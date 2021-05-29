# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from six import string_types
from frappe import _
from frappe.model.document import Document
from banking_api.banking_api.common_provider import CommonProvider
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property
from frappe.core.doctype.version.version import get_diff
from frappe.utils import get_link_to_form

class BankAPIIntegration(Document):
	pass

def initiate_transaction_with_otp(doc, otp):
	workflow_state = None
	integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': doc.company_bank_account})
	disabled_accounts = frappe.get_site_config().bank_api_integration['disable_transaction']

	if disabled_accounts == '*' or integration_doc.account_number in disabled_accounts:
		frappe.throw(_(f'Unable to process transaction for the selected bank account. Please contact Administrator.'))
		return

	res = None
	currency = frappe.db.get_value("Company", doc.company, "default_currency")
	prov, config = get_api_provider_class(doc.company_bank_account)
	filters = {
		"CUSTOMERINDUCED": "N",
		"REMARKS": doc.remarks,
		"OTP": otp,
		"UNIQUEID": doc.name,
		"IFSC": frappe.db.get_value('Bank Account', 
				{'party_type': doc.party_type,
				'party': doc.party,
				'is_default': 1
				},'ifsc_code'),
		"AMOUNT": str(doc.amount),
		"CURRENCY": currency,
		"TXNTYPE": doc.transaction_type,
		"PAYEENAME": doc.party,
		"DEBITACC": integration_doc.account_number,
		"CREDITACC": frappe.db.get_value('Bank Account', 
				{'party_type': doc.party_type,
				'party': doc.party,
				'is_default': 1
				},'bank_account_no')
	}
	try:
		res = prov.initiate_transaction_with_otp(filters)
		if res['status'] == 'SUCCESS' and 'utr_number' in res:
			frappe.db.set_value('Outward Bank Payment',{'name':doc.name},'utr_number',res['utr_number'])
			doc.reload()
			workflow_state = 'Initiated'
		elif res['status'] in ['FAILURE', 'DUPLICATE']:
			workflow_state = 'Initiation Failed'
		elif 'PENDING' in res['status']:
			workflow_state = 'Initiation Pending'
		elif res['status'] in ['OTP EXPIRED', 'INVALID OTP']:
			workflow_state = None
		else:
			workflow_state = 'Initiation Error'
	except:
		workflow_state = 'Initiation Error'
		res = frappe.get_traceback()
	log_name = doc.log_request('Initiate Transaction with OTP', filters, config, res)
	doc.save(ignore_permissions=True)
	doc.reload()
	if workflow_state:
		frappe.db.set_value('Outward Bank Payment', {'name': doc.name}, 'workflow_state', workflow_state)
	if workflow_state in ['Initiation Error', 'Initiation Failed']:
		if not doc.bobp:
			frappe.throw(_(f'An error occurred while making request. Kindly check request log for more info {get_link_to_form("Bank API Request Log", log_name)}'))

def initiate_transaction_without_otp(doc):
	if doc.workflow_state == 'Verified':
		workflow_state = None
		integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': doc.company_bank_account})
		disabled_accounts = frappe.get_site_config().bank_api_integration['disable_transaction']

		if disabled_accounts == '*' or integration_doc.account_number in disabled_accounts:
			frappe.throw(_(f'Unable to process transaction for the selected bank account. Please contact Administrator.'))
			return

		res = None
		currency = frappe.db.get_value("Company", doc.company, "default_currency")
		prov, config = doc.get_api_provider_class(doc.company_bank_account)
		filters = {
			"REMARKS": doc.remarks,
			"UNIQUEID": doc.name,
			"IFSC": frappe.db.get_value('Bank Account', 
					{'party_type': doc.party_type,
					'party': doc.party,
					'is_default': 1
					},'ifsc_code'),
			"AMOUNT": str(doc.amount),
			"CURRENCY": currency,
			"TXNTYPE": doc.transaction_type,
			"PAYEENAME": doc.party,
			"DEBITACC": integration_doc.account_number,
			"CREDITACC": frappe.db.get_value('Bank Account', 
					{'party_type': doc.party_type,
					'party': doc.party,
					'is_default': 1
					},'bank_account_no')
		}
		try:
			res = prov.initiate_transaction_without_otp(filters)
			if res['status'] == 'SUCCESS' and 'utr_number' in res:
				frappe.db.set_value('Outward Bank Payment',{'name':doc.name},'utr_number',res['utr_number'])
				doc.reload()
				workflow_state = 'Initiated'
			elif res['status'] in ['FAILURE', 'DUPLICATE']:
				workflow_state = 'Initiation Failed'
			elif 'PENDING' in res['status']:
				workflow_state = 'Initiation Pending'
			else:
				workflow_state = 'Initiation Error'
		except:
			workflow_state = 'Initiation Error'
			res = frappe.get_traceback()
		log_name = doc.log_request('Initiate Transaction without OTP', filters, config, res)
		doc.save(ignore_permissions=True)
		doc.reload()
		if workflow_state:
			frappe.db.set_value('Outward Bank Payment', {'name': doc.name}, 'workflow_state', workflow_state)
		if workflow_state in ['Initiation Error', 'Initiation Failed']:
			if not doc.bobp:
				frappe.throw(_(f'An error occurred while making request. Kindly check request log for more info {get_link_to_form("Bank API Request Log", log_name)}'))

@frappe.whitelist()
def send_otp(doctype, docname):
	is_otp_sent = False
	res = None
	doc = frappe.get_doc(doctype, docname)
	prov, config = get_api_provider_class(doc.company_bank_account)
	doc.retry_count += 1
	doc.save(ignore_permissions=True)
	doc.reload()
	
	filters = {
		"UNIQUEID": doc.name,
		"AMOUNT": str(doc.amount)
	}
	try:
		res = prov.send_otp(filters)
		if res['status'] == 'SUCCESS':
			is_otp_sent = True
	except:
		res = frappe.get_traceback()
	log_name = log_request('Send OTP', filters, config, res)
	return is_otp_sent

@frappe.whitelist()
def update_transaction_status(obp_name=None,bobp_name=None):
	bulk_update = True
	if obp_name or bobp_name:
		bulk_update = False
	if obp_name:
		obp_list = [{'name': obp_name}]
	if bobp_name:
		obp_list = frappe.db.get_all('Outward Bank Payment', {'workflow_state': ['in', ['Initiated','Initiation Pending','Transaction Pending']], 'bobp': ['=', bobp_name]})
	if bulk_update:
		obp_list = frappe.db.get_all('Outward Bank Payment', {'workflow_state': ['in', ['Initiated','Initiation Pending','Transaction Pending']]})

	failed_obp_list = []
	if not obp_list:
		frappe.throw(_("No transaction found in the initiated state."))
	for doc in obp_list:
		res = None
		workflow_state = None
		obp_doc = frappe.get_doc('Outward Bank Payment', doc['name'])
		prov, config = get_api_provider_class(obp_doc.company_bank_account)
		filters = {"UNIQUEID": obp_doc.name}
		try:
			res = prov.get_transaction_status(filters)
			if res['status'] == 'SUCCESS' and 'utr_number' in res:
				workflow_state = 'Transaction Completed'
			elif res['status'] in ['FAILURE', 'DUPLICATE']:
				workflow_state = 'Transaction Failed'
			elif 'PENDING' in res['status']:
				workflow_state = 'Transaction Pending'
			else:
				workflow_state = 'Transaction Error'
		except:
			workflow_state = 'Transaction Error'
			res = frappe.get_traceback()
		
		log_name = log_request(obp_doc.name,'Update Transaction Status', filters, config, res)
		obp_doc.save(ignore_permissions=True)
		obp_doc.reload()
		frappe.db.set_value('Outward Bank Payment', {'name': obp_doc.name}, 'workflow_state', workflow_state)
		frappe.db.commit()
		if workflow_state in ['Transaction Pending', 'Transaction Error', 'Transaction Failed'] and not bulk_update:
			if not obp_doc.bobp:
				frappe.throw(_(f'An error occurred while making request. Kindly check request log for more info {get_link_to_form("Bank API Request Log", log_name)}'))
			else:
				failed_obp_list.append(get_link_to_form("Outward Bank Payment", doc['name']))
	if failed_obp_list and not bulk_update:
		failed_obp = ','.join(failed_obp_list)
		frappe.throw(_(f"Transaction status update failed for the below obp(s) {failed_obp}"))
	if bobp_name and not bulk_update:
		frappe.msgprint(_("Transaction Status Updated"))

def get_api_provider_class(company_bank_account):
	integration_doc = frappe.get_doc('Bank API Integration', {'bank_account': company_bank_account})
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

def log_request(doc_name, api_method, filters, config, res):
	request_log = frappe.get_doc({
		"doctype": "Bank API Request Log",
		"user": frappe.session.user,
		"reference_document":doc_name,
		"api_method": api_method,
		"filters": json.dumps(filters, indent=4) if filters else None,
		"config_details": json.dumps(config, indent=4),
		"response": json.dumps(res, indent=4)
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

	#Create workflow state
	states_with_style = {'Success': ['Verified','Initiated', 'Transaction Completed', 'Completed'],
	'Danger': ['Verification Failed', 'Initiation Error', 'Initiation Failed', 'Transaction Failed', 'Transaction Error', 'Failed'],
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
		transitions = { 'state': 'Pending',
						'action': state[0],
						'allow_self_approval': 0,
						'next_state': state[1],
						'allowed': 'Bank Checker'}
		workflow_doc.append('transitions',transitions)	
	if document_name == 'Outward Bank Payment':
		optional_states = ['Verified','Verification Failed','Initiated',
				'Initiation Error', 'Initiation Failed', 'Transaction Failed', 'Initiation Pending',
				'Transaction Error', 'Transaction Pending', 'Transaction Completed']
	if document_name == 'Bulk Outward Bank Payment':
		optional_states = ['Verified','Verification Failed','Initiated', 'Processing', 'Partially Completed', 'Completed', 'Failed']

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
		if diff:
			for changed in diff.changed:
				field, old, new = changed
				if field in ['is_verified']:
					frappe.throw('Unauthorized Access')
	elif new_doc.is_verified:
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

@frappe.whitelist()
def get_field_status(bank_account):
	enable_otp_based_transaction = frappe.get_site_config().bank_api_integration['enable_otp_based_transaction']
	acc_num = frappe.db.get_value("Bank API Integration", {"bank_account": bank_account}, "account_number") 
	is_pwd_security_enabled = frappe.db.get_value("Bank API Integration", {"bank_account": bank_account}, "enable_password_security")
	data = {}
	if(enable_otp_based_transaction == '*' or acc_num in enable_otp_based_transaction):
		data['is_otp_enabled'] = 1
	if(is_pwd_security_enabled):
		data['is_pwd_security_enabled'] = 1
	return data

@frappe.whitelist()
def update_status(doctype_name,docname, status):
	frappe.db.set_value(doctype_name, {'name': docname}, 'docstatus', 1)
	frappe.db.set_value(doctype_name, {'name': docname}, 'workflow_state', status)