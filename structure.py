import hashlib
import datetime
import requests
import json
from gmssl import sm2
import random


class Transaction:
    def __init__(self, sender: str | None, receiver: str, amount: float):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.timestamp = str(datetime.datetime.now())
        self.signature = None

    def __str__(self):
        return json.dumps({
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "signature": self.signature
        }, ensure_ascii=False)

    @classmethod
    def load_from_json(cls, json_dump: str):
        ins = cls(str(), str(), float())
        obj = json.loads(json_dump)
        ins.sender = obj["sender"]
        ins.receiver = obj["receiver"]
        ins.amount = obj["amount"]
        ins.timestamp = obj["timestamp"]
        ins.signature = obj["signature"]
        return ins

    def sign(self, private_key, public_key):
        cryptSM2 = sm2.CryptSM2(private_key, public_key)
        data = str(self.sender) + str(self.receiver) + str(self.amount) + str(self.timestamp)
        signature = cryptSM2.sign(data.encode(), str(random.randint(1000, 10000000)))
        return signature

    def calculate_hash(self):
        data = str(self.sender) + str(self.receiver) + str(self.amount) + str(self.timestamp)
        return hashlib.sha256(data.encode()).hexdigest()


class Block:
    def __init__(self, transactions: list[Transaction], previous_hash):
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = str(datetime.datetime.now())
        self.nonce = 0
        self.hash = self.calculate_hash()

    def __str__(self):
        return json.dumps({
            "transactions": [str(transaction) for transaction in self.transactions],
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "hash": self.hash
        }, ensure_ascii=False)

    @classmethod
    def load_from_json(cls, json_dump: str):
        ins = cls(list(), str())
        obj = json.loads(json_dump)
        transaction_dicts = obj["transactions"]
        ins.transactions = [Transaction.load_from_json(transaction_dict) for transaction_dict in transaction_dicts]
        ins.previous_hash = obj["previous_hash"]
        ins.timestamp = obj["timestamp"]
        ins.nonce = obj["nonce"]
        ins.hash = obj["hash"]
        return ins

    def calculate_hash(self):
        data = str([transaction.calculate_hash() for transaction in self.transactions]) + str(self.previous_hash) + \
               str(self.timestamp) + str(self.nonce)
        return hashlib.sha256(data.encode()).hexdigest()

    def mine_block(self, difficulty):
        target = "0" * difficulty

        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()


class Blockchain:
    def __init__(self):
        self.chain = []
        self.difficulty = 1
        self.pending_transactions = []
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block([], "0")
        self.chain.append(genesis_block)

    def get_last_block(self):
        return self.chain[-1]

    def add_transaction(self, transaction):
        self.pending_transactions.append(transaction)

    def mine_pending_transactions(self, miner_node_id, peers_table: dict):
        block = Block(self.pending_transactions, self.get_last_block().hash)
        block.mine_block(self.difficulty)

        self.chain.append(block)
        self.pending_transactions = []

        # Reward the miner with a transaction
        reward_transaction = Transaction(None, miner_node_id, 10)
        self.pending_transactions.append(reward_transaction)

        for _, (address, _) in peers_table.items():
            requests.post(f"http://{address}/receive_block", json={
                "block": str(block),
                "reward_transaction": str(reward_transaction)
            })

    def get_balance(self, node_id):
        balance = 0
        income = 0
        expenditure = 0

        for block in self.chain + [Block(self.pending_transactions, 0)]:
            for transaction in block.transactions:
                if transaction.sender == node_id:
                    balance -= transaction.amount
                    expenditure += transaction.amount
                if transaction.receiver == node_id:
                    balance += transaction.amount
                    income += transaction.amount

        return balance, income, expenditure
