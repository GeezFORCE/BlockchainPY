import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4
import requests
from flask import Flask, jsonify, request

class blockchain:
    def __init__(self):
        self.curr_transactions = []
        self.chain = []
        self.nodes = set()
        self.new_block(prev_hash='1', proof=100)

    def reg_new_node(self, address):
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('URL not defined')

    def valid_chain(self, chain):
        latest_block = chain[0]
        curr_index = 1
        while curr_index < len(chain):
            block = chain[curr_index]
            print(f'{latest_block}')
            print(f'{block}')
            if curr_index == self.hash(latest_block):
                return False
            latest_block = block
            curr_index += 1
        return True

    def conflict_resolution(self):
        others=self.nodes
        new_chain=None
        max_len = len(self.chain)
        for node in others:
            res = requests.get(f'http://{node}/chain')
            if res.status_code == 200:
                leng = res.json()['length']
                chain = res.json()['chain']
                if leng > max_len and self.valid_chain(chain):
                    max_len = leng
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False

    def new_block(self, proof, prev_hash):
        block = {
            'index': len(self.chain)+1,
            'timestamp': time(),
            'transactions': self.curr_transactions,
            'proof': proof,
            'prev_hash': prev_hash or self.hash(self.chain[-1]),
        }
        self.curr_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        self.curr_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        return self.last_block['index']+1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        block_str = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_str).hexdigest()

    def proof_work(self, last_block):
        last_proof_work = last_block['proof']
        last_hash = self.hash(last_block)
        proof = 0
        while self.valid_proof(last_proof_work, proof, last_hash) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof_work, proof, last_hash):
        guess = f'{last_proof_work}{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


app = Flask(__name__)
node_id = str(uuid4()).replace('-', '')
block_chain = blockchain()
@app.route('/mine', methods=['GET'])
def mine():
    last_block = block_chain.last_block
    proof = block_chain.proof_work(last_block)
    block_chain.new_transaction(sender="0", recipient=node_id, amount=1,)
    prev_hash = block_chain.hash(last_block)
    block=block_chain.new_block(proof, prev_hash)
    res = {
        'message': "Created New Block",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'prev_hash': block['prev_hash'],
    }
    return jsonify(res), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing Values', 400
    index = block_chain.new_transaction(
        values['sender'], values['recipient'], values['amount'])
    res = {'message': f'Transaction added to Block{index}'}
    return jsonify(res), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    res = {
        'chain': block_chain.chain,
        'length': len(block_chain.chain),
    }
    return jsonify(res), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        block_chain.reg_new_node(node)

    res = {
        'message': 'New nodes have been added',
        'total_nodes': list(block_chain.nodes),
    }
    return jsonify(res), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = block_chain.conflict_resolution()
    if replaced:
        res = {
            'message': 'Chain was modified',
            'new_chain': block_chain.chain
        }
    else:
        res = {
            'message': 'Our chain is not modified',
            'chain': block_chain.chain
        }
    return jsonify(res), 200


if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000,
                        type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port()

    app.run(host='0.0.0.0', port=port)
