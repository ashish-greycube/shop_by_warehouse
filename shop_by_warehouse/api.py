from erpnext.e_commerce.product_data_engine.query import ProductQuery
import frappe
import json
from erpnext.e_commerce.product_data_engine.filters import ProductFiltersBuilder
from erpnext.setup.doctype.item_group.item_group import get_child_groups_for_website
from frappe.utils import cint
@frappe.whitelist(allow_guest=True)
def get_product_filter_data(query_args=None):
	"""
	Returns filtered products and discount filters.
	:param query_args (dict): contains filters to get products list

	Query Args filters:
	search (str): Search Term.
	field_filters (dict): Keys include item_group, brand, etc.
	attribute_filters(dict): Keys include Color, Size, etc.
	start (int): Offset items by
	item_group (str): Valid Item Group
	from_filters (bool): Set as True to jump to page 1
	"""
	if isinstance(query_args, str):
		query_args = json.loads(query_args)

	query_args = frappe._dict(query_args)
	if query_args:
		search = query_args.get("search")
		field_filters = query_args.get("field_filters", {})
		attribute_filters = query_args.get("attribute_filters", {})
		start = cint(query_args.start) if query_args.get("start") else 0
		item_group = query_args.get("item_group")
		from_filters = query_args.get("from_filters")
	else:
		search, attribute_filters, item_group, from_filters = None, None, None, None
		field_filters = {}
		start = 0

	# if new filter is checked, reset start to show filtered items from page 1
	if from_filters:
		start = 0

	sub_categories = []
	if item_group:
		sub_categories = get_child_groups_for_website(item_group, immediate=True)

	engine = CustomProductQuery()
	try:
		result = engine.query(
			attribute_filters, field_filters, search_term=search, start=start, item_group=item_group
		)
	except Exception:
		frappe.log_error("Product query with filter failed")
		return {"exc": "Something went wrong!"}

	# discount filter data
	filters = {}
	discounts = result["discounts"]

	if discounts:
		filter_engine = ProductFiltersBuilder()
		filters["discount_filters"] = filter_engine.get_discount_filters(discounts)

	return {
		"items": result["items"] or [],
		"filters": filters,
		"settings": engine.settings,
		"sub_categories": sub_categories,
		"items_count": result["items_count"],
	}







class CustomProductQuery(ProductQuery):
	def query_items(self, start=0):
		print('@@'*100)
		#  find if there is Ecommerce warehouse in filter
		custom_filter_name='Ecommerce Warehouse'
		filter_index_to_remove=-1
		custom_filter_values=None
		warehouse_to_search=None
		for i,row in enumerate(self.filters):
			if custom_filter_name in row:
				filter_index_to_remove=i
				custom_filter_values=row
				break
		if filter_index_to_remove!=-1:
			self.filters.pop(filter_index_to_remove)
		if custom_filter_values:
			warehouse_to_search=custom_filter_values[3]


		"""Build a query to fetch Website Items based on field filters."""
		# MySQL does not support offset without limit,
		# frappe does not accept two parameters for limit
		# https://dev.mysql.com/doc/refman/8.0/en/select.html#id4651989
		count_items = frappe.db.get_all(
			"Website Item",
			filters=self.filters,
			or_filters=self.or_filters,
			limit_page_length=184467440737095516,
			limit_start=start,  # get all items from this offset for total count ahead
			order_by="ranking desc",
		)
		count = len(count_items)
		


		# If discounts included, return all rows.
		# Slice after filtering rows with discount (See `filter_results_by_discount`).
		# Slicing before hand will miss discounted items on the 3rd or 4th page.
		# Discounts are fetched on computing Pricing Rules so we cannot query them directly.
		page_length = 184467440737095516 if self.filter_with_discount else self.page_length

		items = frappe.db.get_all(
			"Website Item",
			fields=self.fields,
			filters=self.filters,
			or_filters=self.or_filters,
			limit_page_length=page_length,
			limit_start=start,
			order_by="ranking desc",
		)
		if warehouse_to_search and len(items)>0:
			new_item_list=[]
			print('warehouse_string',len(warehouse_to_search),warehouse_to_search)
			for item in items:
				# actual_qty = frappe.db.sql(
				# 	"""select warehouse,actual_qty from tabBin where warehouse in (%s)"""
				# 	%", ".join(["%s"] * len(warehouse_to_search)),tuple(warehouse_to_search))
				item_code=item.get("item_code")
				print('item_code',item)
				actual_qty = frappe.db.sql(
					"""select warehouse,actual_qty from tabBin 
					where item_code = %s and warehouse in ({})""".format(", ".join(["%s"] * len(warehouse_to_search))),
					tuple([item_code]+warehouse_to_search),as_dict=1)
				if len(actual_qty)>0:
					# item.website_warehouse=actual_qty[0].warehouse
					# frappe.db.set_value('Website Item', item.name, 'website_warehouse', actual_qty[0].warehouse)
					new_item_list.append(item)
				else:
					count=count-1
			items=new_item_list
					
				# actual_qty = frappe.db.sql(
				# 	"""select warehouse,actual_qty from tabBin where item_code=%s and warehouse in ({0})"""
				# 	.format(", ".join(["%s"] * len(warehouse_to_search))),tuple([item.item_code+warehouse_to_search]),)				
		return items, count