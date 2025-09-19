import frappe

def get_or_create_link(doctype, value, fieldname="name"):
    if not value:
        return None

    existing = frappe.db.get_value(doctype, {fieldname: value}, "name")
    if existing:
        return existing

    doc = frappe.get_doc({
        "doctype": doctype,
        fieldname: value
    })
    doc.flags.ignore_validate = True
    doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_if_duplicate=True)
    return doc.name


def get_or_create_select(doctype, fieldname, value):
    if not value:
        return None

    meta = frappe.get_meta(doctype)
    field = next((f for f in meta.fields if f.fieldname == fieldname and f.fieldtype == "Select"), None)

    if not field:
        return value  

    options = field.options.split("\n") if field.options else []

    if value not in options:
        options.append(value)
        frappe.db.set_value("DocField", field.name, "options", "\n".join(options))
        frappe.clear_cache(doctype=doctype)

    return value


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_donor():
    try:
        data = frappe.local.form_dict

        donor = frappe.get_doc({
            "doctype": "Donor",
            "donor_name": data.get("donor_name"),
            "donor_identity": data.get("donor_identity"),
            # "owner_id": data.get("owner_id"),   
            "donor_dob": data.get("donor_dob"),

            # Link fields
            "donor_type": get_or_create_link("Donor Type", data.get("donor_type"), "donor_type"),
            "department": get_or_create_link("Department", data.get("department"), "department_name"),
            "gender": get_or_create_link("Gender", data.get("gender"), "gender"),
            "branch": get_or_create_link("Cost Center", data.get("branch"), "cost_center_name"),
            "donor_desk": get_or_create_link("Donor Desk", data.get("desk_name"), "donor_desk"),
            "city": get_or_create_link("City", data.get("city"), "city_name"),
            "state": get_or_create_link("Province", data.get("state"), "province"),
            "country": get_or_create_link("Country", data.get("country"), "country_name"),
            "designation": get_or_create_link("Designation", data.get("designation"), "designation_name"),
            "co_designation": get_or_create_link("Designation", data.get("co_designation"), "designation_name"),
            "representative_designation": get_or_create_link("Designation", data.get("representative_designation"), "designation_name"),
            "org_representative_designation": get_or_create_link("Designation", data.get("org_representative_designation"), "designation_name"),
            "individual_country": get_or_create_link("Country", data.get("individual_country"), "country_name"),
            "orgs_country": get_or_create_link("Country", data.get("orgs_country"), "country_name"),
            "companys_interest_in_services": get_or_create_link("Service Area", data.get("companys_interest_in_services"), "service_name"),
            "custom_campaign": get_or_create_link("Campaign", data.get("custom_campaign"), "campaign_name"),

            # # Select fields
            "identification_type": get_or_create_select("Donor", "identification_type", data.get("identification_type")),
            "donor_identity": get_or_create_select("Donor", "donor_identity", data.get("donor_identity")),
            "relationship_with_donor": get_or_create_select("Donor", "relationship_with_donor", data.get("relationship_with_donor")),
            "company_type": get_or_create_select("Donor", "company_type", data.get("company_type")),
            "profession__business_category": get_or_create_select("Donor", "profession__business_category", data.get("profession__business_category")),
            "no_of_company__employees": get_or_create_select("Donor", "no_of_company__employees", data.get("no_of_company__employees")),
            "nationality_type": get_or_create_select("Donor", "nationality_type", data.get("nationality_type")),
            "profession": get_or_create_select("Donor", "profession", data.get("profession")),
            "org__category": get_or_create_select("Donor", "org__category", data.get("org__category")),
            "org_sector": get_or_create_select("Donor", "org_sector", data.get("org_sector")),

            # # Direct fields
            "cnic": data.get("cnic"),
            "contact_no": data.get("contact_no"),
            "email": data.get("email"),
            "address": data.get("address"),
            "co_name": data.get("co_name"),
            "co_contact_no": data.get("co_contact_no"),
            "co_email": data.get("co_email"),
            "co_address": data.get("co_address"),
            "area": data.get("area"),
            "co_city": data.get("co_city"),
            "co_country": data.get("co_country"),
            "company_name": data.get("company_name"),
            "company_owner_ceo_name": data.get("company_owner_ceo_name"),
            "company_ownerceo_name": data.get("company_ownerceo_name"),
            "company_website": data.get("company_website"),
            "company_email_address": data.get("company_email_address"),
            "company_turnover": data.get("company_turnover"),
            "representative_mobile": data.get("representative_mobile"),
            "representative_email": data.get("representative_email"),
            "registration_date": data.get("registration_date"),
            "companyorg": data.get("companyorg"),
            "phone_no": data.get("phone_no"),
            "mobile_no": data.get("mobile_no"),
            "individual_city": data.get("individual_city"),
            "org_name": data.get("org_name"),
            "org_website": data.get("org_website"),
            "org_contact": data.get("org_contact"),
            "org_head_of_board": data.get("org_head_of_board"),
            "org_head_of_board_email": data.get("org_head_of_board_email"),
            "org_head_of_board_mobile": data.get("org_head_of_board_mobile"),
        })
        
        donor.flags.ignore_validate = True
        donor.insert(ignore_permissions=True, ignore_mandatory=True, ignore_if_duplicate=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Donor created successfully (validations skipped + select options handled)",
            "donor_name": donor.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Donor API Error")
        return {
            "status": "error",
            "message": str(e)
        }
