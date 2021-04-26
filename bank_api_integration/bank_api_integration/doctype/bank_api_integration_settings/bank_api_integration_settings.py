# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import banking_api
from banking_api.common_provider import CommonProvider
from frappe import _
from frappe.utils import getdate
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

class BankAPIIntegrationSettings(Document):
	pass

# provider  = frappe.db.get_single_value('Bank API Integration Settings', 'bank_api_provider')
# if not provider:
# 	provider = 'Test'
# prov = CommonProvider(provider)

# @frappe.whitelist()
# def fetch_balance():
# 	return prov.fetch_balance()

# @frappe.whitelist()
# def sync_transactions():
# 	try:
# 		transactions = prov.fetch_statement()

# 		result = []
# 		for transaction in reversed(transactions):
# 			result += new_bank_transaction(transaction)

# 		if result:
# 			frappe.logger().info("Bank API added {} new Bank Transactions".format(
# 				len(result)))
# 	except Exception:
# 		frappe.log_error(frappe.get_traceback(), _("Banking API transactions sync error"))


def new_bank_transaction(transaction):
	result = []
	bank_account = frappe.db.get_value("Bank Account", dict(bank_account_no=transaction["account_no"]))
	if not frappe.db.exists("Bank Transaction", dict(transaction_id=transaction["txn_id"])):
		new_transaction = frappe.get_doc({
			'doctype': 'Bank Transaction',
			'date': getdate(transaction['txn_date'].split(' ')[0]),
			"transaction_id": transaction["txn_id"],
			'withdrawal': abs(float(transaction['debit'].replace(',',''))) if transaction['debit'] else 0,
			'deposit': abs(float(transaction['credit'].replace(',',''))) if transaction['credit'] else 0,
			'description': transaction['remarks'],
			'bank_account': bank_account
		})
		new_transaction.save()
		new_transaction.submit()
		result.append(new_transaction.name)
	return result

def create_defaults():
	#Create default roles
	roles = ['Bank Maker','Bank Checker']
	for role in roles:
		if not frappe.db.exists('Role', role):
			role_doc = frappe.new_doc("Role")
			role_doc.role_name = role
			role_doc.save()

	#Create custom field
	custom_fields = {
	'Bank Account': [
	{
		"fieldname": "ifsc_code",
		"fieldtype": "Data",
		"label": "IFSC Code",
		"insert_after" : "iban"
	},
	]
	}
	create_custom_fields(
		custom_fields, ignore_validate=frappe.flags.in_patch, update=True)

	#Create workflow action master
	frappe.get_doc({'doctype': 'Workflow Action Master',
			'workflow_action_name': 'Invoke'}).save()

	#Create workflow state
	states_with_style = {'Success': ['Initiated', 'Transaction Completed'],
	'Danger': ['Initiation Error', 'Initiation Failed', 'Transaction Failed', 'Transaction Error'],
	'Primary': ['Transaction Pending']}

	for style in states_with_style.keys():
		for state in states_with_style[style]:
			if not frappe.db.exists('Workflow State', state):
				frappe.get_doc({"doctype" : "Workflow State",
								"workflow_state_name" : state,
								"style" : style}).save()

	create_workflow('Outward Bank Payment')
	create_workflow('Bulk Outward Bank Payment')

def create_workflow(document_name):
	#Create default workflow
	workflow_doc = frappe.get_doc({'doctype': 'Workflow',
			'workflow_name': f'{document_name} Workflow',
			'document_type': document_name,
			'workflow_state_field': 'workflow_state',
			'is_active': 1})

	bank_checker_allowed_state = ['Approved', 'Rejected']
	
	if document_name == 'Outward Bank Payment':
		bank_checker_allowed_state += ['Initiated',
				'Initiation Error', 'Initiation Failed', 'Transaction Failed',
				'Transaction Error', 'Transaction Pending', 'Transaction Completed']
	workflow_doc.append('states',{'state': 'Pending',
				'doc_status': 0,
				'update_field': 'status',
				'update_value': 'Pending',
				'allow_edit': 'Bank Maker'})

	for state in bank_checker_allowed_state:
		workflow_doc.append('states',{'state': state,
					'doc_status': 1,
					'update_field': 'status',
					'update_value': state,
					'allow_edit': 'Bank Checker'})

	pending_next_states = [['Approve', 'Approved'], ['Reject', 'Rejected']]
	approved_next_states = {'Invoke': ['Initiated', 'Initiation Error', 'Initiation Failed']}
	initiated_next_states = {'Invoke': ['Transaction Error', 'Transaction Failed', 'Transaction Pending', 'Transaction Completed']}
	for state in pending_next_states:
		workflow_doc.append('transitions',{'state': 'Pending',
			'action': state[0],
			'next_state': state[1],
			'allowed': 'Bank Checker'})
	if document_name == 'Outward Bank Payment':
		for state in approved_next_states['Invoke']:
			workflow_doc.append('transitions',{'state': 'Approved',
				'action': 'Invoke',
				'next_state': state,
				'allowed': 'Bank Checker'})
		for state in initiated_next_states['Invoke']:
			workflow_doc.append('transitions',{'state': 'Initiated',
				'action': 'Invoke',
				'next_state': state,
				'allowed': 'Bank Checker'})

	workflow_doc.save()