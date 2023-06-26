from flask import Flask, jsonify, request, render_template
import hashlib
import requests
import json
from gmssl import sm2
import sm2_util
from structure import Transaction, Block, Blockchain
import webbrowser

app = Flask(__name__, static_url_path='', static_folder='templates', template_folder='templates')

blockchain = Blockchain()
# The peers_table is a dictionary,
# whose form of every pair is ((`Node ID` that isSHA-256 encrypted server address) : [`server addresses`, `public key`])
peers_table = {}
host = "127.0.0.1"
port = 5000
node_address = f"{host}:{port}"
node_id = hashlib.sha256(node_address.encode()).hexdigest()
private_key = ""
public_key = ""


@app.route('/home')
def webpage_home():
    balance, income, expenditure = 0, 0, 0
    transaction_record = []  # Form: [isSender, the other node ID, time, amount]
    for block in blockchain.chain + [Block(blockchain.pending_transactions, 0)]:
        for transaction in block.transactions:
            if transaction.sender == node_id:
                balance -= transaction.amount
                expenditure += transaction.amount
                transaction_record.append([True, transaction.receiver, transaction.timestamp, transaction.amount])
            if transaction.receiver == node_id:
                balance += transaction.amount
                income += transaction.amount
                transaction_record.append([False, "Mining" if transaction.sender is None else transaction.sender,
                                           transaction.timestamp, transaction.amount])
    return render_template("index.html", node_address=node_address, node_id=node_id, public_key=public_key,
                           private_key=private_key, balance=balance, income=income, expenditure=expenditure,
                           transaction_record=json.dumps(transaction_record),
                           receiver_array=json.dumps(list(peers_table.keys())))


@app.route('/chain', methods=['GET'])
def get_full_chain():
    response = {
        'chain': [str(block) for block in blockchain.chain],
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200


@app.route('/peers_table', methods=['GET'])
def get_peers_table():
    return jsonify(peers_table), 200


@app.route('/public_key', methods=['GET'])
def get_public_key():
    return public_key, 200


@app.route('/pending_transactions', methods=['GET'])
def get_pending_transactions():
    return jsonify(list(map(str, blockchain.pending_transactions))), 200


# When a miner mines a block, this endpoint will be request by miner's node.
@app.route('/receive_block', methods=['POST'])
def receive_block():
    request_obj = request.get_json()
    block = Block.load_from_json(request_obj["block"])
    reward_transaction = Transaction.load_from_json(request_obj["reward_transaction"])
    if validate_new_block(block):
        blockchain.chain.append(block)
        blockchain.pending_transactions = [reward_transaction]
        return jsonify({'message': 'Blockchain synchronized successfully.', 'error': 0})
    else:
        return jsonify({'message': 'Invalid block.', 'error': 1})


@app.route('/register_node', methods=['POST'])
def register_node():
    register_node_address = request.get_json()['node_address']
    register_node_public_key = request.get_json()['public_key']
    peers_table[hashlib.sha256(register_node_address.encode()).hexdigest()] = \
        [register_node_address, register_node_public_key]
    return jsonify({'message': 'Node added successfully.', 'error': 0})


@app.route('/receive_transaction', methods=['POST'])
def receive_transaction():
    transaction = Transaction.load_from_json(request.json["transaction"])
    is_valid = verify_transaction(transaction)

    if is_valid:
        # Add the received transaction to the pending transactions list in the blockchain
        blockchain.add_transaction(transaction)
        return jsonify({'message': 'Transaction received and added to the pending transactions.', 'error': 0})
    else:
        return jsonify({'message': 'Invalid transaction.', 'error': 1})


@app.route('/create_transaction', methods=['POST'])
def create_transaction():
    request_obj = request.get_json()
    make_transaction(Transaction(node_id, request_obj['receiver'], request_obj['amount']))
    return jsonify({'message': 'The transaction was added successfully.', 'error': 0})


@app.route('/mine', methods=['POST'])
def start_mine():
    blockchain.mine_pending_transactions(node_id, peers_table)
    return jsonify({'message': 'Have mined successfully.', 'error': 0})


def make_transaction(transaction: Transaction):
    # Add the transaction to the pending transactions list in the blockchain
    transaction.signature = transaction.sign(private_key, public_key)
    blockchain.add_transaction(transaction)
    # Broadcast the transaction to other nodes in the network
    for _, (address, _) in peers_table.items():
        requests.post(f"http://{address}/receive_transaction", json={"transaction": str(transaction)})


def verify_transaction(transaction):
    data = str(transaction.sender) + str(transaction.receiver) + str(transaction.amount) + str(transaction.timestamp)
    try:
        cryptSM2 = sm2.CryptSM2(None, peers_table[transaction.sender][1])
        return cryptSM2.verify(transaction.signature, data.encode())
    except ArithmeticError:
        return False


def validate_chain(chain: list[Block]):
    # Verify the integrity and validity of the received chain
    for i in range(1, len(chain)):
        current_block = chain[i]
        previous_block = chain[i - 1]
        if current_block.previous_hash != previous_block.hash or \
                current_block.hash != current_block.calculate_hash():
            return False
    return True


def validate_new_block(block):
    # Verify the integrity and validity of the received block

    current_block = block
    previous_block = blockchain.get_last_block()

    return current_block.previous_hash == previous_block.hash and current_block.hash == current_block.calculate_hash()


def fresh_to_network(valid_node_address: str, my_node_address: str):
    global peers_table, private_key, public_key

    try:
        private_key, public_key = sm2_util.create_key_pair()

        peers_table_response = requests.get(f"http://{valid_node_address}/peers_table")
        valid_node_public_key = requests.get(f"http://{valid_node_address}/public_key").text
        peers_table = peers_table_response.json()
        peers_table[hashlib.sha256(valid_node_address.encode()).hexdigest()] = \
            [valid_node_address, valid_node_public_key]

        for _, (address, _) in peers_table.items():
            requests.post(f"http://{address}/register_node",
                          json={"node_address": my_node_address, "public_key": public_key})

        requests.post(f"http://{valid_node_address}/register_node",
                      json={"node_address": my_node_address, "public_key": public_key})

        blockchain_response = requests.get(f"http://{valid_node_address}/chain")
        received_blockchain = [Block.load_from_json(block) for block in
                               blockchain_response.json()["chain"]]
        if validate_chain(received_blockchain):
            blockchain.chain = received_blockchain
        else:
            raise Exception("Cannot initialize blockchain from a invalid node.")

        pending_transactions = requests.get(f"http://{valid_node_address}/pending_transactions").json()
        pending_transactions = list(map(Transaction.load_from_json, pending_transactions))
        blockchain.pending_transactions = pending_transactions

    except (requests.exceptions.ConnectionError, requests.exceptions.InvalidURL):
        peers_table = {}


def start(ser_host=host, ser_port=port, valid_address: str = ""):
    global host, port, node_address, node_id
    host = ser_host
    port = ser_port

    node_address = f"{host}:{port}"
    node_id = hashlib.sha256(node_address.encode()).hexdigest()

    webbrowser.open(f"http://{node_address}/home")
    fresh_to_network(valid_address, node_address)

    app.run(host=ser_host, port=ser_port)
