import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../../lib/api';
import { useAuth } from '../../lib/auth';
import styles from './UserManagement.module.css';

const UserManagement = () => {
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    role: '',
    status: '',
    search: ''
  });
  const [pagination, setPagination] = useState({
    page: 1,
    per_page: 20,
    total: 0,
    pages: 0
  });
  const [showUserDetails, setShowUserDetails] = useState(false);

  useEffect(() => {
    if (!currentUser || (currentUser.role !== 'admin' && currentUser.role !== 'super_admin')) {
      navigate('/dashboard');
      return;
    }

    fetchUsers();
  }, [currentUser, navigate, filters, pagination.page]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: pagination.page,
        per_page: pagination.per_page,
        ...filters
      });

      const response = await api.get(`/admin/users?${params}`);
      setUsers(response.data.users);
      setPagination(prev => ({
        ...prev,
        ...response.data.pagination
      }));
      setError(null);
    } catch (err) {
      setError('Failed to fetch users');
      console.error('Users fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserDetails = async (userId) => {
    try {
      const response = await api.get(`/admin/users/${userId}`);
      setSelectedUser(response.data);
      setShowUserDetails(true);
    } catch (err) {
      setError('Failed to fetch user details');
      console.error('User details fetch error:', err);
    }
  };

  const handleUserAction = async (userId, action, data = {}) => {
    try {
      const endpoints = {
        suspend: `/admin/users/${userId}/suspend`,
        role: `/admin/users/${userId}/role`
      };

      const response = await api.post(endpoints[action], data);

      // Update local state
      setUsers(prev => prev.map(user =>
        user.id === userId
          ? { ...user, ...response.data.user }
          : user
      ));

      if (selectedUser && selectedUser.user.id === userId) {
        setSelectedUser(prev => ({
          ...prev,
          user: { ...prev.user, ...response.data.user }
        }));
      }

    } catch (err) {
      setError(`Failed to ${action} user`);
      console.error(`${action} user error:`, err);
    }
  };

  const UserCard = ({ user }) => {
    const [showActions, setShowActions] = useState(false);
    const [showConfirmDialog, setShowConfirmDialog] = useState(false);
    const [action, setAction] = useState('');
    const [actionData, setActionData] = useState({});

    const getStatusBadge = (isActive) => (
      <span className={`${styles.statusBadge} ${isActive ? styles.active : styles.inactive}`}>
        {isActive ? 'Active' : 'Suspended'}
      </span>
    );

    const getRoleBadge = (role) => {
      const roleStyles = {
        student: styles.studentRole,
        admin: styles.adminRole,
        super_admin: styles.superAdminRole
      };

      return (
        <span className={`${styles.roleBadge} ${roleStyles[role] || styles.studentRole}`}>
          {role?.replace('_', ' ').toUpperCase() || 'STUDENT'}
        </span>
      );
    };

    const handleAction = () => {
      switch (action) {
        case 'suspend':
          handleUserAction(user.id, 'suspend', {
            suspend: true,
            reason: actionData.reason || 'Administrative action'
          });
          break;
        case 'unsuspend':
          handleUserAction(user.id, 'suspend', {
            suspend: false,
            reason: 'Account restored'
          });
          break;
        case 'role':
          handleUserAction(user.id, 'role', {
            role: actionData.role,
            reason: actionData.reason || 'Role update by admin'
          });
          break;
      }
      setShowConfirmDialog(false);
      setAction('');
      setActionData({});
    };

    const canEditUser = currentUser.role === 'super_admin' ||
                      (currentUser.role === 'admin' && user.role !== 'super_admin');

    return (
      <>
        <motion.div
          className={styles.userCard}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          whileHover={{ y: -2 }}
          onMouseEnter={() => setShowActions(true)}
          onMouseLeave={() => setShowActions(false)}
        >
          <div className={styles.userHeader}>
            <div className={styles.userInfo}>
              <div className={styles.userAvatar}>
                {user.username.charAt(0).toUpperCase()}
              </div>
              <div className={styles.userDetails}>
                <h3 className={styles.userName}>{user.username}</h3>
                <p className={styles.userEmail}>{user.email}</p>
                <div className={styles.userMeta}>
                  {getStatusBadge(user.is_active)}
                  {getRoleBadge(user.role)}
                  <span className={styles.joinDate}>
                    Joined {new Date(user.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>

            <AnimatePresence>
              {showActions && canEditUser && (
                <motion.div
                  className={styles.userActions}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                >
                  <button
                    onClick={() => fetchUserDetails(user.id)}
                    className={styles.actionButton}
                    title="View Details"
                  >
                    👁️
                  </button>

                  {user.is_active ? (
                    <button
                      onClick={() => {
                        setAction('suspend');
                        setShowConfirmDialog(true);
                      }}
                      className={styles.actionButton}
                      title="Suspend User"
                    >
                      ⏸️
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        setAction('unsuspend');
                        setShowConfirmDialog(true);
                      }}
                      className={styles.actionButton}
                      title="Unsuspend User"
                    >
                      ▶️
                    </button>
                  )}

                  {currentUser.role === 'super_admin' && (
                    <button
                      onClick={() => {
                        setAction('role');
                        setShowConfirmDialog(true);
                      }}
                      className={styles.actionButton}
                      title="Change Role"
                    >
                      👑
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className={styles.userStats}>
            <div className={styles.stat}>
              <span className={styles.statValue}>{user.stats?.tasks_count || 0}</span>
              <span className={styles.statLabel}>Tasks</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statValue}>{user.stats?.model_runs_count || 0}</span>
              <span className={styles.statLabel}>Model Runs</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statValue}>{user.stats?.custom_models_count || 0}</span>
              <span className={styles.statLabel}>Custom Models</span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statValue}>
                {user.stats?.last_login ? new Date(user.stats.last_login).toLocaleDateString() : 'Never'}
              </span>
              <span className={styles.statLabel}>Last Login</span>
            </div>
          </div>

          {/* Confirmation Dialog */}
          <AnimatePresence>
            {showConfirmDialog && (
              <motion.div
                className={styles.confirmDialog}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className={styles.confirmContent}>
                  <h3>
                    {action === 'suspend' && 'Suspend User'}
                    {action === 'unsuspend' && 'Unsuspend User'}
                    {action === 'role' && 'Change User Role'}
                  </h3>

                  {action === 'role' && (
                    <select
                      value={actionData.role || ''}
                      onChange={(e) => setActionData({ ...actionData, role: e.target.value })}
                      className={styles.roleSelect}
                    >
                      <option value="">Select Role</option>
                      <option value="student">Student</option>
                      <option value="admin">Admin</option>
                      <option value="super_admin">Super Admin</option>
                    </select>
                  )}

                  {(action === 'suspend' || action === 'unsuspend') && (
                    <textarea
                      placeholder="Reason for action (optional)"
                      value={actionData.reason || ''}
                      onChange={(e) => setActionData({ ...actionData, reason: e.target.value })}
                      className={styles.reasonInput}
                      rows={3}
                    />
                  )}

                  <div className={styles.confirmActions}>
                    <button
                      onClick={() => setShowConfirmDialog(false)}
                      className={styles.cancelButton}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleAction}
                      className={styles.confirmButton}
                      disabled={action === 'role' && !actionData.role}
                    >
                      Confirm
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </>
    );
  };

  const UserDetailsModal = () => {
    if (!selectedUser || !showUserDetails) return null;

    const { user, resource_usage, recent_activity } = selectedUser;

    return (
      <motion.div
        className={styles.detailsModal}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={() => setShowUserDetails(false)}
      >
        <motion.div
          className={styles.detailsContent}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={styles.detailsHeader}>
            <h2>User Details: {user.username}</h2>
            <button
              onClick={() => setShowUserDetails(false)}
              className={styles.closeButton}
            >
              ✕
            </button>
          </div>

          <div className={styles.detailsBody}>
            {/* Basic Information */}
            <section className={styles.detailSection}>
              <h3>Basic Information</h3>
              <div className={styles.detailGrid}>
                <div className={styles.detailItem}>
                  <label>Username</label>
                  <span>{user.username}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Email</label>
                  <span>{user.email}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Role</label>
                  <span>{user.role?.replace('_', ' ').toUpperCase()}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Status</label>
                  <span className={user.is_active ? 'text-green-600' : 'text-red-600'}>
                    {user.is_active ? 'Active' : 'Suspended'}
                  </span>
                </div>
                <div className={styles.detailItem}>
                  <label>Joined</label>
                  <span>{new Date(user.created_at).toLocaleString()}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Last Login</label>
                  <span>
                    {user.last_login
                      ? new Date(user.last_login).toLocaleString()
                      : 'Never'
                    }
                  </span>
                </div>
              </div>
            </section>

            {/* Resource Usage */}
            <section className={styles.detailSection}>
              <h3>Resource Usage</h3>
              <div className={styles.detailGrid}>
                <div className={styles.detailItem}>
                  <label>Total Tasks</label>
                  <span>{resource_usage?.total_tasks || 0}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Model Runs</label>
                  <span>{resource_usage?.total_model_runs || 0}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Custom Models</label>
                  <span>{resource_usage?.total_custom_models || 0}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Successful Runs</label>
                  <span>{resource_usage?.successful_runs || 0}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Failed Runs</label>
                  <span>{resource_usage?.failed_runs || 0}</span>
                </div>
                <div className={styles.detailItem}>
                  <label>Account Age</label>
                  <span>{resource_usage?.account_age_days || 0} days</span>
                </div>
              </div>
            </section>

            {/* Recent Activity */}
            <section className={styles.detailSection}>
              <h3>Recent Activity</h3>
              <div className={styles.activityList}>
                {recent_activity?.length > 0 ? (
                  recent_activity.map((activity, index) => (
                    <div key={index} className={styles.activityItem}>
                      <div className={styles.activityModel}>
                        {activity.model_id_str}
                      </div>
                      <div className={styles.activityStatus}>
                        <span className={`${styles.statusIndicator} ${styles[activity.status.toLowerCase()]}`}>
                          {activity.status}
                        </span>
                      </div>
                      <div className={styles.activityTime}>
                        {new Date(activity.created_at).toLocaleString()}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className={styles.noActivity}>No recent activity</p>
                )}
              </div>
            </section>
          </div>
        </motion.div>
      </motion.div>
    );
  };

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <p>Loading users...</p>
      </div>
    );
  }

  return (
    <div className={styles.userManagement}>
      <div className={styles.pageHeader}>
        <h1>User Management</h1>
        <button
          onClick={() => navigate('/admin')}
          className={styles.backButton}
        >
          ← Back to Dashboard
        </button>
      </div>

      {/* Filters */}
      <div className={styles.filters}>
        <div className={styles.filterGroup}>
          <input
            type="text"
            placeholder="Search users..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className={styles.searchInput}
          />
        </div>

        <div className={styles.filterGroup}>
          <select
            value={filters.role}
            onChange={(e) => setFilters({ ...filters, role: e.target.value })}
            className={styles.filterSelect}
          >
            <option value="">All Roles</option>
            <option value="student">Student</option>
            <option value="admin">Admin</option>
            <option value="super_admin">Super Admin</option>
          </select>
        </div>

        <div className={styles.filterGroup}>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className={styles.filterSelect}
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Suspended</option>
          </select>
        </div>
      </div>

      {/* Results Summary */}
      <div className={styles.resultsSummary}>
        <span>
          Showing {users.length} of {pagination.total} users
        </span>
      </div>

      {/* Error Message */}
      {error && (
        <div className={styles.errorMessage}>
          <span>⚠️ {error}</span>
          <button onClick={fetchUsers}>Retry</button>
        </div>
      )}

      {/* Users List */}
      <div className={styles.usersList}>
        <AnimatePresence>
          {users.map((user) => (
            <UserCard key={user.id} user={user} />
          ))}
        </AnimatePresence>

        {users.length === 0 && !loading && (
          <div className={styles.noResults}>
            <p>No users found matching your criteria</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {pagination.pages > 1 && (
        <div className={styles.pagination}>
          <button
            onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
            disabled={pagination.page === 1}
            className={styles.paginationButton}
          >
            Previous
          </button>

          <span className={styles.paginationInfo}>
            Page {pagination.page} of {pagination.pages}
          </span>

          <button
            onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
            disabled={pagination.page === pagination.pages}
            className={styles.paginationButton}
          >
            Next
          </button>
        </div>
      )}

      {/* User Details Modal */}
      <UserDetailsModal />
    </div>
  );
};

export default UserManagement;