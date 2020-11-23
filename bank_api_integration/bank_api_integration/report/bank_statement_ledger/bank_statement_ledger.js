// Copyright (c) 2016, Aerele and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Bank Statement Ledger"] = {
	"filters": [
		{
			"fieldname":"effective_balance",
			"label": __("Effective Balance"),
			"fieldtype": "Currency",
			"default": 0,
			"read_only": 1
		},
	]
};
