# Authorization Update Summary

## Changes Made

### Issue: Users Could See Other Users' Requests
**Problem:** Any user could see all requests from all users, and unauthenticated users could browse requests.

**Solution:** Implemented proper authorization:
1. **Backend**: Added authentication and authorization checks
2. **Frontend**: Protected routes and updated UI
3. **Tests**: Added comprehensive test coverage

---

## Backend Changes (`backend/main.py`)

### 1. Protected `/api/requests` Endpoint

**Before:**
```python
@app.get("/api/requests", ...)
def list_requests(status: Optional[str] = None, department_id: Optional[str] = None):
    """Return all RTI requests."""
    results = list(_db["requests"])
    # ... filtering logic
```

**After:**
```python
@app.get("/api/requests", ...)
def list_requests(
    current_user: UserPublic = Depends(get_current_user),  # ← Now requires auth
    status: Optional[str] = None, 
    department_id: Optional[str] = None
):
    """Return RTI requests for the authenticated user.
    Admins can see all requests; regular users only see their own."""
    results = list(_db["requests"])
    
    # Non-admin users can only see their own requests
    if not current_user.is_admin:
        results = [r for r in results if r["email"] == current_user.email]
    
    # ... filtering logic
```

### 2. Protected `/api/requests/{request_id}` Endpoint

**Before:**
```python
@app.get("/api/requests/{request_id}", ...)
def get_request(request_id: str):
    """Return a single RTI request by its id."""
    for req in _db["requests"]:
        if req["id"] == request_id:
            return req
    raise HTTPException(status_code=404, ...)
```

**After:**
```python
@app.get("/api/requests/{request_id}", ...)
def get_request(
    request_id: str,
    current_user: UserPublic = Depends(get_current_user),  # ← Now requires auth
):
    """Return a single RTI request by its id.
    Users can only access their own requests; admins can access all."""
    for req in _db["requests"]:
        if req["id"] == request_id:
            # Check authorization
            if not current_user.is_admin and req["email"] != current_user.email:
                raise HTTPException(status_code=403, detail="Permission denied")
            return req
    raise HTTPException(status_code=404, ...)
```

---

## Frontend Changes (`frontend/src/App.jsx`)

### 1. Updated RequestsPage to Use Authenticated Fetch

**Before:**
```javascript
function RequestsPage() {
  const { data: requests, loading, error } = useFetch("/api/requests");
  // ...
  return (
    <PageWrapper>
      <PageTitle>RTI Requests</PageTitle>
      <Subtitle>Browse and track all filed Right to Information requests.</Subtitle>
```

**After:**
```javascript
function RequestsPage() {
  const { data: requests, loading, error } = useAuthedFetch("/api/requests");  // ← Uses auth
  // ...
  return (
    <PageWrapper>
      <PageTitle>My RTI Requests</PageTitle>
      <Subtitle>Track your filed Right to Information requests and their status.</Subtitle>
```

### 2. Updated RequestDetailPage to Use Authenticated Fetch

**Before:**
```javascript
function RequestDetailPage() {
  const { id } = useParams();
  const { data: req, loading, error } = useFetch(`/api/requests/${id}`);
```

**After:**
```javascript
function RequestDetailPage() {
  const { id } = useParams();
  const { data: req, loading, error } = useAuthedFetch(`/api/requests/${id}`);  // ← Uses auth
```

### 3. Protected Routes with RequireAuth

**Before:**
```javascript
<Route path="/requests" element={<RequestsPage />} />
<Route path="/requests/:id" element={<RequestDetailPage />} />
```

**After:**
```javascript
<Route path="/requests" element={
  <RequireAuth><RequestsPage /></RequireAuth>
} />
<Route path="/requests/:id" element={
  <RequireAuth><RequestDetailPage /></RequireAuth>
} />
```

### 4. Hidden Navigation Links for Unauthenticated Users

**Before:**
```javascript
{ to: "/requests", label: "Requests" },
{ to: "/requests/new", label: "File RTI" },
```

**After:**
```javascript
...(user ? [{ to: "/requests", label: "Requests" }] : []),
...(user ? [{ to: "/requests/new", label: "File RTI" }] : []),
```

### 5. Removed Citizen Name Column from Requests Table

Since users only see their own requests, the "Citizen" column is redundant.

**Before:** `["ID", "Citizen", "Department", "Subject", "Status", "Date Filed"]`

**After:** `["ID", "Department", "Subject", "Status", "Date Filed"]`

---

## Test Changes

### Updated Tests (`backend/tests/test_auth.py`)

1. **Renamed test:**
   - `test_public_endpoints_remain_open` → Now correctly excludes `/api/requests`

2. **New test:**
   - `test_protected_endpoints_require_auth` - Verifies GET endpoints require auth

3. **New test:**
   - `test_users_can_only_see_their_own_requests` - Comprehensive authorization test

### New Admin Test (`backend/tests/test_admin.py`)

- `test_admin_can_see_all_requests_but_citizens_only_their_own` - Verifies:
  - Admins see all requests
  - Citizens only see their own
  - Citizens get 403 when accessing others' requests
  - Admins can access any request

---

## Authorization Matrix

| User Type | GET /api/requests | GET /api/requests/:id | Sees Other Users' Data |
|-----------|-------------------|----------------------|----------------------|
| **Unauthenticated** | 401 Unauthorized | 401 Unauthorized | ❌ No access |
| **Regular User** | ✅ Only their requests | ✅ Only their requests | ❌ No (403 Forbidden) |
| **Admin** | ✅ All requests | ✅ All requests | ✅ Yes |

---

## Security Improvements

### Before:
- ❌ Unauthenticated users could browse all requests
- ❌ Users could see other users' personal information
- ❌ Users could access other users' request details
- ❌ No privacy protection

### After:
- ✅ Authentication required for all request endpoints
- ✅ Users can only see their own data
- ✅ Admins have elevated permissions (can see all)
- ✅ 403 Forbidden for unauthorized access attempts
- ✅ Protected routes in frontend
- ✅ Hidden navigation for unauthenticated users

---

## User Experience

### For Regular Users:
1. Must log in to see the "Requests" and "File RTI" navigation links
2. Can only view their own requests
3. Get a clear error if trying to access another user's request
4. See personalized page title: "My RTI Requests"

### For Admin Users:
1. Can see all requests from all users
2. Can access any request detail page
3. Can use the admin panel to manage requests
4. Have full visibility for oversight purposes

### For Unauthenticated Users:
1. Cannot see request-related navigation links
2. Redirected to login if trying to access protected pages
3. Can still access public pages (Home, Departments, FAQs)

---

## Testing

Run the test suite to verify:

```bash
cd backend
python -m pytest tests/test_auth.py::test_users_can_only_see_their_own_requests -v
python -m pytest tests/test_admin.py::test_admin_can_see_all_requests_but_citizens_only_their_own -v
```

Or run all tests:
```bash
python -m pytest -v
```

---

## Migration Notes

**For existing deployments:**

No database migration needed since this only affects authorization logic. However:

1. Users will need to log in to see their requests
2. Previously public request URLs will now require authentication
3. Unauthenticated users will be redirected to login

**Breaking Changes:**
- GET `/api/requests` now requires authentication (was public)
- GET `/api/requests/:id` now requires authentication (was public)
- Regular users cannot see other users' requests anymore

These are **intentional security improvements** to protect user privacy.
