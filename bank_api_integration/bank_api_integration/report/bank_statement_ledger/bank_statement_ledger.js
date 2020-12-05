// Copyright (c) 2016, Aerele and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Bank Statement Ledger"] = {
	"filters": [
		{
			"fieldname":"account_no",
			"label": __("Account No"),
			"fieldtype": "Data",
			"read_only": 1
		},
		{
			"fieldname":"date",
			"label": __("Date"),
			"fieldtype": "Data",
			"read_only": 1
		},
		{
			"fieldname":"balance",
			"label": __("Balance"),
			"fieldtype": "Data",
			"read_only": 1
		},
		{
			"fieldname":"currency",
			"label": __("Currency"),
			"fieldtype": "Data",
			"read_only": 1
		}
	],
	onload: function(frm)
	{
	frappe.call({
	method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration_settings.bank_api_integration_settings.fetch_balance",
	freeze: true,
	callback: function(r) {
		if(r.message) {
		frappe.query_report.set_filter_value('account_no',r.message['account_no']);
		frappe.query_report.set_filter_value('date',r.message['date']);
		frappe.query_report.set_filter_value('balance',r.message['balance']);
		frappe.query_report.set_filter_value('currency',r.message['currency']);
		}
	}
		});
	}
};
