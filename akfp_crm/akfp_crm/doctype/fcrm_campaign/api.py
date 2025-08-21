# Copyright (c) 2025, Nabeel Saleem and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, get_datetime, get_time, get_url, now_datetime
from frappe.model.document import Document


@frappe.whitelist()
def get_campaign(name):
	"""Get campaign details"""
	if not frappe.has_permission("FCRM Campaign", "read", name):
		frappe.throw("Not permitted", frappe.PermissionError)
	
	campaign = frappe.get_doc("FCRM Campaign", name)
	return campaign.as_dict()


@frappe.whitelist()
def create_new(doc):
	"""Create new campaign"""
	if not frappe.has_permission("FCRM Campaign", "create"):
		frappe.throw("Not permitted", frappe.PermissionError)
	
	doc = frappe.get_doc(doc)
	doc.insert()
	return doc.as_dict()


@frappe.whitelist()
def update_campaign(name, fieldname, value):
	"""Update campaign field"""
	if not frappe.has_permission("FCRM Campaign", "write", name):
		frappe.throw("Not permitted", frappe.PermissionError)
	
	frappe.db.set_value("FCRM Campaign", name, fieldname, value)
	return frappe.get_doc("FCRM Campaign", name).as_dict()


@frappe.whitelist()
def delete_campaign(name):
	"""Delete campaign"""
	if not frappe.has_permission("FCRM Campaign", "delete", name):
		frappe.throw("Not permitted", frappe.PermissionError)
	
	frappe.delete_doc("FCRM Campaign", name)
	return {"message": "Campaign deleted successfully"}


@frappe.whitelist()
def search_campaigns(search_term, limit=20):
	"""Search campaigns by name"""
	if not frappe.has_permission("FCRM Campaign", "read"):
		frappe.throw("Not permitted", frappe.PermissionError)
	
	campaigns = frappe.get_list(
		"FCRM Campaign",
		filters={"campaign_name": ["like", f"%{search_term}%"]},
		fields=["name", "campaign_name", "description"],
		limit=limit
	)
	return campaigns 