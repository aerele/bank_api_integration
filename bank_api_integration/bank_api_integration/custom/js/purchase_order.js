frappe.ui.form.on('Purchase Order', {
    refresh : function(frm){
        if(frm.doc.docstatus == 1 && frm.doc.grand_total != 0) {
            // Creating Make Bank Payment Button
            frm.add_custom_button(__('Make Bank Payment'), () =>{
            frm.trigger("make_bank_payment");
         },__('Create'));
    }
    },
    make_bank_payment : function(frm) {
        frappe.model.open_mapped_doc({
        method: "bank_api_integration.bank_api_integration.doctype.outward_bank_payment.outward_bank_payment.bank_payment_for_purchase_order",
        frm: frm
    })
},
});