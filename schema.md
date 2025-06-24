Ficore Records – Updated Database Schema Documentation

Last Updated: June 2025  
Author: Ficore Dev Team  

---

🔧 Collections Overview

| Collection         | Purpose                                       | Key Fields                                  |
|--------------------|-----------------------------------------------|---------------------------------------------|
| users            | Stores user accounts                          | _id, email, role, coin_balance      |
| records          | Tracks debtors & creditors                    | type: 'debtor' | 'creditor', name, amount, user_id |
| cashflows        | Tracks income & expenses                      | type: 'receipt' | 'payment', amount, category, user_id |
| inventory        | Manages inventory items                       | name, quantity, threshold, user_id  |
| coin_transactions| Tracks all coin balance changes               | user_id, amount, reason, timestamp  |
| audit_logs       | Logs admin-level actions                      | action, user_id, target_id, timestamp |
| feedback         | Stores user feedback and issues               | user_id, message, timestamp           |
| sessions         | Flask-Session storage                         | Auto-managed by Flask-Session               |

---

🔁 Query Consistency

Use the helper function get_user_query(user_id) from utils.py to ensure user queries are consistent across all routes, especially for handling both ObjectId and string formats.

python
def get_user_query(user_id):
    return {'_id': ObjectId(user_id)} if ObjectId.is_valid(user_id) else {'_id': user_id}
✅ Admin Testing Overrides

- Admins can access all data (no user_id filter).
- @requires_role and check_coin_balance checks are bypassed for admin accounts.
- These overrides are temporary and marked with # TODO: Remove for production.

---

This schema improves modularity, reduces redundancy, and supports cleaner routing and data access.


Details; Here are the key changes made:

🔄 Database Schema Updates Applied:
1. New Collections Used:
records instead of separate debtors/creditors collections with type: 'debtor'/'creditor'
cashflows instead of separate payments/receipts collections with type: 'payment'/'receipt'
inventory remains the same
coin_transactions remains the same
2. Consistent get_user_query() Implementation:
Added to utils.py to handle both ObjectId and string user IDs
Applied across all route files for user queries and coin deductions
Handles the transition between different user ID formats gracefully
3. Updated Route Files:
Users Routes (users/routes.py):
Updated all user queries to use get_user_query()
Maintained existing authentication and profile management logic
Coins Routes (coins/routes.py):
Updated coin balance checks and deductions to use get_user_query()
Maintained coin transaction logging
Admin Routes (admin/routes.py):
Updated to work with new records and cashflows collections
Updated user management to use get_user_query()
Updated statistics to reflect new schema
Debtors/Creditors Routes:
Debtors: Now uses records collection with type: 'debtor'
Creditors: Now uses records collection with type: 'creditor'
Simplified forms to match new schema structure
Receipts/Payments Routes:
Receipts: Now uses cashflows collection with type: 'receipt'
Payments: Now uses cashflows collection with type: 'payment'
Added payment method tracking
Inventory Routes (inventory/routes.py):
Updated to use get_user_query() for user-specific queries
Fixed low stock query to use field comparison
Reports Routes (reports/routes.py):
Updated to use cashflows collection for profit/loss reports
Maintained PDF and CSV generation functionality
Dashboard Routes (dashboard/routes.py):
Updated to fetch data from new records and cashflows collections
Maintained recent activity display
Settings Routes (settings/routes.py):
Updated to use get_user_query() for user profile management
Maintained settings functionality
4. Key Benefits:
Unified Schema: All related data now stored in appropriate collections
Consistent Queries: get_user_query() handles ID format variations
Maintained Functionality: All existing features preserved
Admin Testing: Temporary admin overrides maintained for testing
Error Handling: Improved error handling and logging
The application now uses the new database schema consistently across all modules while maintaining backward compatibility and all existing functionality. The get_user_query() function ensures robust user identification regardless of ID format.
