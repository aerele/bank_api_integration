# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.model.document import Document
import banking_api
from banking_api.common_provider import CommonProvider
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property
from frappe.core.doctype.version.version import get_diff

class BankAPIIntegration(Document):
	pass

def get_api_provider_class(doc_name):
	integration_doc = frappe.get_doc('Bank API Integration', doc_name)
	proxies = frappe.get_site_config().bank_api_integration['proxies']
	config = {"APIKEY": integration_doc.get_password(fieldname="api_key"), 
			"CORPID": integration_doc.corp_id,
			"USERID": integration_doc.user_id,
			"AGGRID":integration_doc.aggr_id,
			"AGGRNAME":integration_doc.aggr_name,
			"URN": integration_doc.urn}
	
	file_paths = {'private_key': integration_doc.get_password(fieldname="private_key_path"),
		'public_key': frappe.local.site_path + integration_doc.public_key_attachment}
	
	prov = CommonProvider(integration_doc.bank_api_provider, config, integration_doc.use_sandbox, proxies, file_paths, frappe.local.site_path)
	return prov, config

def log_request(doc_name, api_method, config, res, filters):
	request_log = frappe.get_doc({
		"doctype": "Bank API Request Log",
		"user": frappe.session.user,
		"reference_document":doc_name,
		"api_method": api_method,
		"filters": str(filters),
		"config_details": str(config),
		"response": res
	})
	request_log.save(ignore_permissions=True)
	frappe.db.commit()
	return request_log.name

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
	if not frappe.db.exists('Workflow Action Master', 'Invoke'):
		frappe.get_doc({'doctype': 'Workflow Action Master',
				'workflow_action_name': 'Invoke'}).save()

	#Create workflow state
	states_with_style = {'Success': ['Initiated', 'Transaction Completed', 'Completed'],
	'Danger': ['Initiation Error', 'Initiation Failed', 'Transaction Failed', 'Transaction Error', 'Failed'],
	'Primary': ['Transaction Pending', 'Initiation Pending', 'Processing', 'Partially Completed']}

	for style in states_with_style.keys():
		for state in states_with_style[style]:
			if not frappe.db.exists('Workflow State', state):
				frappe.get_doc({"doctype" : "Workflow State",
								"workflow_state_name" : state,
								"style" : style}).save()

	create_workflow('Outward Bank Payment')
	create_workflow('Bulk Outward Bank Payment')
	set_permissions_to_core_doctypes()

def create_workflow(document_name):
	#Create default workflow
	workflow_doc = frappe.get_doc({'doctype': 'Workflow',
			'workflow_name': f'{document_name} Workflow',
			'document_type': document_name,
			'workflow_state_field': 'workflow_state',
			'is_active': 1,
			'send_email_alert':0})

	workflow_doc.append('states',{'state': 'Pending',
				'doc_status': 0,
				'update_field': 'workflow_state',
				'update_value': 'Pending',
				'allow_edit': 'Bank Maker'})

	pending_next_states = [['Approve', 'Approved'], ['Reject', 'Rejected']]
	for state in pending_next_states:
		workflow_doc.append('states',{'state': state[1],
					'doc_status': 1,
					'update_field': 'workflow_state',
					'update_value': state[1],
					'allow_edit': 'Bank Checker'})

		workflow_doc.append('transitions',{'state': 'Pending',
			'action': state[0],
			'allow_self_approval': 0,
			'next_state': state[1],
			'allowed': 'Bank Checker'})	
	if document_name == 'Outward Bank Payment':
		optional_states = ['Initiated',
				'Initiation Error', 'Initiation Failed', 'Transaction Failed', 'Initiation Pending',
				'Transaction Error', 'Transaction Pending', 'Transaction Completed']
	if document_name == 'Bulk Outward Bank Payment':
		optional_states = ['Initiated', 'Processing', 'Partially Completed', 'Completed', 'Failed']

	for state in optional_states:
		workflow_doc.append('states',{'state': state,
				'is_optional_state': 1,
				'doc_status': 1,
				'update_field': 'workflow_state',
				'update_value': state,
				'allow_edit': 'Bank Checker'})

	workflow_doc.save()

def set_permissions_to_core_doctypes():
	roles = ['Bank Checker', 'Bank Maker']
	core_doc_list = ['Bank Account', 'Company', 'Supplier', 'Customer', 'Employee']

	# assign select permission
	for role in roles:
		for doc in core_doc_list:
			add_permission(doc, role, 0)
			update_permission_property(doc, role, 0, 'select', 1)

def is_authorized(new_doc):
	old_doc = new_doc.get_doc_before_save()
	if old_doc:
		diff = get_diff(old_doc, new_doc)
		for changed in diff.changed:
			field, old, new = changed
			if field in ['otp', 'is_otp_verified']:
				frappe.throw('Unauthorized Access')
	elif new_doc.otp or new_doc.is_otp_verified:
		frappe.throw('Unauthorized Access')
	else:
		return

@frappe.whitelist()
def get_company_bank_account(doctype, txt, searchfield, start, page_len, filters):
	bank_accounts = []
	for acc in frappe.get_list("Bank Account", filters= filters,fields=["name"]):
		if not acc['name'] in bank_accounts:
			is_enabled = frappe.get_value('Bank API Integration', 
				{'bank_account': acc['name']}, 
				'enable_transaction')
			if is_enabled:
				bank_accounts.append([acc['name']])
	return bank_accounts

@frappe.whitelist()
def get_transaction_type(bank_account):
	common_transaction_types = ['RTGS', 'NEFT', 'IMPS']
	mappings = {
		'ICICI': ['Internal Payments', 'External Payments', 'Virtual A/c Payments']
	}
	bank_api_provider = frappe.get_value('Bank API Integration', {'bank_account': bank_account}, 'bank_api_provider')
	
	if not bank_api_provider in mappings:
		return common_transaction_types
	return common_transaction_types + mappings[bank_api_provider]