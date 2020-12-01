# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import banking_api
from banking_api.common_provider import CommonProvider

class BankBalance(Document):
	pass

provider  = frappe.db.get_single_value('Bank API Integration Settings', 'bank_api_provider')
prov = CommonProvider(provider)

def fetch_balance():
	bal = prov.fetch_balance()
	if not frappe.db.exists('Bank Balance', bal):
		bal['doctype'] = 'Bank Balance'
		frappe.get_doc(bal).save()

