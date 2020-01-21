#!/usr/bin/env python
# encoding:utf-8

from flask import Flask, jsonify, request
import hashlib
import json
import os
import requests
import sys
from textwrap import dedent
from time import time
from urllib.parse import urlparse
from uuid import uuid4


class Blockchain(object):
	def __init__(self):
		self.chain = []
		self.current_transactions = []
		self.nodes = set()
		# create the genesis block
		self.new_block(proof=100, previous_hash=1)
	
	def register_node(self, address):
		"""
		add a new node to the list of nodes

		:param address: <str> address of the new node. Eg. 'http://localhost:3000'
		:return: None
		"""
		parsed_url = urlparse(address)
		self.nodes.add(parsed_url.netloc)
	
	# pass
	
	def valid_chain(self, chain):
		"""
		determine if a given blockchain is valid

		:param chain: <list> a blockchain
		:return: <bool> True if valid, False if not
		"""
		last_block = chain[0]
		current_index = 1
		
		while current_index < len(chain):
			block = chain[current_index]
			print(f'{last_block}')
			print(f'{block}')
			print("\n---------------\n")
			# check that the hash of the block is correct or not
			if block['previous_hash'] != self.hash(last_block):
				return False
			
			# check that the proof of work is correct
			if not self.valid_proof(last_block['proof'], block['proof']):
				return False
			
			last_block = block
			current_index += 1
		
		return True
	
	def resolve_conflicts(self):
		"""
		this is our confilct algorithm, it resolve the conflicts by replacing our chain with the longest one in the network

		"return: <bool>, True if our chain was replaced, False if not
		"""
		neighbours = self.nodes
		new_chain = None
		
		# we are only looking for the longer chains than ours
		max_length = len(self.chain)
		
		for node in neighbours:
			response = requests.get(f'http://{node}/chain')
			
			if response.status_code == 200:
				length = response.json()['length']
				chain = response.json()['chain']
			
			# check if the length is longer and the chain is valid
			if length > max_length and self.valid_chain(chain):
				max_length = length
				new_chain = chain
		
		# replace our chain if we discovered a new, longer and valid chain
		if new_chain:
			self.chain = new_chain
			return True
		
		return False
	
	def new_block(self, proof, previous_hash=None):
		# creates a new block and adds it to the chain
		'''
		create new block in the blockchain
		:param proof: <int>the proof given by the Proof of work algorithm
		:param previous_hash: (optional) <str> hash of previous block
		:return: <dict> new block
		'''
		block = {
			'index': len(self.chain) + 1,
			'timestamp': time(),
			'transactions': self.current_transactions,
			'proof': proof,
			'previous_hash': previous_hash or self.hash(self.chain[-1])
		}
		
		# reset the current list transactions
		self.current_transactions = []
		
		self.chain.append(block)
		
		return block
	
	# pass
	
	def new_transaction(self, sender, recipient, amount):
		# adds a new transaction to the list of the transactions
		'''
		create a new transaction to go into next mined block
		:param sender: <Str> address of the sender
		:param recipient: <Str> address of the recipient
		:param amount: <Int> amount
		:return: <Int> the index of the block that will hold the transaction
		'''
		self.current_transactions.append({
			"sender": sender,
			"recipient": recipient,
			"amount": amount,
		})
		
		return self.last_block['index'] + 1
	
	# pass
	
	@staticmethod
	def hash(block):
		# hashes a block
		'''
		create a sha-256 hash of a block
		:param block: <dict> block
		:return: <str>
		'''
		# we must make sure theat he dictionary is ordered, or we'll have inconsistent hashes
		block_string = json.dumps(block, sort_keys=True).encode()
		return hashlib.sha256(block_string).hexdigest()
	
	# pass
	
	@property
	def last_block(self):
		# return the last block in the chain
		return self.chain[-1]
	
	# pass
	
	def proof_of_work(self, last_proof):
		"""
		simple proof of work algorithm
		-find a number p', such that hash(pp') contains leading 4 zeros, where p is the privious p'
		-p is the previous proof, and p' is the new proof

		:param last_proof: <int>
		:return: <int>
		"""
		proof = 0
		while self.valid_proof(last_proof, proof) is False:
			proof += 1
		
		return proof
	
	# pass
	
	@staticmethod
	def valid_proof(last_proof, proof):
		"""
		validates the proof: does hash(last_proof, proof) contain 4 leading zeros?

		:param last_proof: <int> previous proof
		:param proof: <int> current proof
		:return: <bool> True if correct, False if not
		"""
		
		guess = f'{last_proof}{proof}'.encode()
		guess_hash = hashlib.sha256(guess).hexdigest()
		return guess_hash[:4] == "0000"


# Instantiate our node
app = Flask(__name__)

# Generate a global unique address of this node
node_identifier = str(uuid4()).replace('-', '')

# instantiate the blockchain
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
	# return 'we will mine a block'
	# we run the proof of work algorithm to get the next proof
	last_block = blockchain.last_block
	last_proof = last_block['proof']
	proof = blockchain.proof_of_work(last_proof)
	
	# we must reward the miner a new block for finding the proof of work
	# the sender is "0" to signify that this node has mined a new block
	blockchain.new_transaction(sender="0", recipient=node_identifier, amount=1)
	
	# forge the new block by adding it to the blockchain
	previous_hash = blockchain.hash(last_block)
	block = blockchain.new_block(proof, previous_hash)
	
	response = {
		'message': 'new block forged',
		'index': block['index'],
		'transactions': block['transactions'],
		'proof': block['proof'],
		'previous_hash': block['previous_hash'],
	}
	
	return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
	# return 'we will add a new transaction'
	values = request.get_json()
	# check that the required fields are in the post data
	required = ['sender', 'recipient', 'amount']
	if not all(k in values for k in required):
		return 'Missing value', 400
	
	# create a new transaction
	index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
	response = {'message': f'transaction will be add to blockchain {index}'}
	
	return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
	response = {
		'chain': blockchain.chain,
		'length': len(blockchain.chain),
	}
	
	return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
	values = request.get_json()
	
	nodes = values.get('nodes')
	
	if nodes is None:
		return 'Error, please supply a valid list of nodes', 400
	
	for node in nodes:
		blockchain.register_node(node)
	
	response = {
		'message': 'new nodes have been added',
		'total_nodes': list(blockchain.nodes),
	}
	
	return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
	replaced = blockchain.resolve_conflicts()
	
	if replaced:
		response = {
			'message': 'our chain has been relplaced',
			'new_chain': blockchain.chain,
		}
	else:
		response = {
			'message': 'our chain is authoritative',
			'new_chain': blockchain.chain,
		}
	
	return jsonify(response), 200


if __name__ == '__main__':
	port = int(sys.argv[1])
	# print(f'{port}')
	app.run(host='0.0.0.0', port=port)