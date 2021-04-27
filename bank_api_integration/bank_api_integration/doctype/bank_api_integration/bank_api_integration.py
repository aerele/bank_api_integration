# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
import banking_api
from banking_api.common_provider import CommonProvider

class BankAPIIntegration(Document):
	pass

@frappe.whitelist()
def fetch_balance(doc_name):
	prov, config = get_api_provider_class(doc_name)
	filters = {"ACCOUNTNO": frappe.db.get_value('Bank API Integration', {'name': doc_name}, 'account_number')}
	balance = 0
	try:
		res = prov.fetch_balance(filters)
		res = frappe._dict(json.loads(res))
		if res["RESPONSE"] == "SUCCESS":
			balance = res['EFFECTIVEBAL']
	except:
		res = frappe.get_traceback()
	log_name = log_request(doc_name,'Fetch Balance', config, res, filters)
	return balance

def get_api_provider_class(doc_name):
	integration_doc = frappe.get_doc('Bank API Integration', doc_name)
	proxies = frappe.get_site_config().proxies
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