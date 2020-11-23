# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import banking_api
from banking_api.CommonProvider import CommonProvider

class BankStatement(Document):
	pass

def fetch_statement():
	provider  = frappe.db.get_single_value('Bank API Integration Settings', 'bank_api_provider')
	prov = CommonProvider(provider)
	for stmt in prov.fetch_statement():
		stmt['doctype'] = "Bank Statement"
		if frappe.db.exists('Bank Statement', {'txn_date': stmt['txn_date'], 'balance': stmt['balance']}):
			frappe.get_doc(stmt).save()