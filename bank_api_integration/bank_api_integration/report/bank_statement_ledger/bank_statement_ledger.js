// Copyright (c) 2016, Aerele and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Bank Statement Ledger"] = {
	"filters": [
		{
			"fieldname":"effective_balance",
			"label": __("Effective Balance"),
			"fieldtype": "Currency",
			"read_only": 1
		},
	],
	onload: function(frm)
	{
		frappe.call({
			method: "bank_api_integration.bank_api_integration.doctype.bank_statement.bank_statement.fetch_balance",
			freeze: true,
			callback: function(r) {
			  if(r.message) {
				frappe.query_report.set_filter_value('effective_balance',r.message);
			  }
			}
		  });
	}
};
