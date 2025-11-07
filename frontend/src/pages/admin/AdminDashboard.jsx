import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from 'recharts';
import api from '../../lib/api';
import { useAuth } from '../../lib/auth';
import styles from './AdminDashboard.module.css';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

const AdminDashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState(30); // days

  useEffect(() => {
    if (!user || (user.role !== 'admin' && user.role !== 'super_admin')) {
      navigate('/dashboard');
      return;
    }

    fetchAnalytics();
  }, [user, navigate, timeRange]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/admin/analytics?days=${timeRange}`);
      setAnalytics(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch analytics data');
      console.error('Analytics fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const MetricCard = ({ title, value, subtitle, icon, color, trend }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${styles.metricCard} ${styles[color]}`}
    >
      <div className={styles.metricHeader}>
        <div className={styles.metricIcon}>
          {icon}
        </div>
        <div className={styles.metricValue}>
          {value}
          {trend && <span className={styles.trend}>{trend}</span>}
        </div>
      </div>
      <div className={styles.metricTitle}>{title}</div>
      <div className={styles.metricSubtitle}>{subtitle}</div>
    </motion.div>
  );

  const SystemHealthIndicator = ({ status, label }) => {
    const statusColors = {
      healthy: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444'
    };

    return (
      <div className={styles.healthIndicator}>
        <div
          className={styles.healthDot}
          style={{ backgroundColor: statusColors[status] }}
        />
        <span>{label}</span>
      </div>
    );
  };

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <p>Loading admin dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.errorContainer}>
        <div className={styles.errorIcon}>⚠️</div>
        <h3>Error Loading Dashboard</h3>
        <p>{error}</p>
        <button onClick={fetchAnalytics} className={styles.retryButton}>
          Retry
        </button>
      </div>
    );
  }

  const systemMetrics = analytics?.system_metrics || [];
  const usersByRole = analytics?.users?.by_role || [];
  const modelRunsByStatus = analytics?.model_runs?.by_status || [];

  return (
    <div className={styles.adminDashboard}>
      <div className={styles.dashboardHeader}>
        <h1>Admin Dashboard</h1>
        <div className={styles.headerControls}>
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(parseInt(e.target.value))}
            className={styles.timeRangeSelect}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={fetchAnalytics}
            className={styles.refreshButton}
            title="Refresh dashboard"
          >
            🔄
          </button>
        </div>
      </div>

      {/* System Health */}
      <div className={styles.section}>
        <h2>System Health</h2>
        <div className={styles.healthGrid}>
          <SystemHealthIndicator status="healthy" label="Database" />
          <SystemHealthIndicator status="healthy" label="Redis Cache" />
          <SystemHealthIndicator status="healthy" label="Worker Queue" />
          <SystemHealthIndicator status="warning" label="Disk Space" />
        </div>
      </div>

      {/* Key Metrics */}
      <div className={styles.section}>
        <h2>Platform Overview</h2>
        <div className={styles.metricsGrid}>
          <MetricCard
            title="Total Users"
            value={analytics?.users?.total || 0}
            subtitle={`${analytics?.users?.new || 0} new this period`}
            icon="👥"
            color="blue"
            trend={analytics?.users?.new > 0 ? `+${analytics.users.new}` : null}
          />
          <MetricCard
            title="Active Users"
            value={analytics?.users?.active || 0}
            subtitle="Logged in within period"
            icon="✅"
            color="green"
          />
          <MetricCard
            title="Total Tasks"
            value={analytics?.tasks?.total || 0}
            subtitle={`${analytics?.tasks?.new || 0} new this period`}
            icon="📋"
            color="purple"
          />
          <MetricCard
            title="Model Runs"
            value={analytics?.model_runs?.total || 0}
            subtitle={`${analytics?.model_runs?.new || 0} new this period`}
            icon="🤖"
            color="orange"
          />
          <MetricCard
            title="Custom Models"
            value={analytics?.custom_models?.total || 0}
            subtitle={`${analytics?.custom_models?.new || 0} new this period`}
            icon="🧠"
            color="pink"
          />
          <MetricCard
            title="Export Jobs"
            value={analytics?.exports?.total || 0}
            subtitle={`${analytics?.exports?.new || 0} new this period`}
            icon="📤"
            color="cyan"
          />
          <MetricCard
            title="Security Events"
            value={analytics?.security?.events_in_period || 0}
            subtitle="Security incidents this period"
            icon="🔒"
            color={analytics?.security?.events_in_period > 10 ? "red" : "green"}
          />
        </div>
      </div>

      {/* Charts */}
      <div className={styles.chartsGrid}>
        {/* User Distribution */}
        <div className={styles.chartCard}>
          <h3>Users by Role</h3>
          {usersByRole.length > 0 && (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={usersByRole.map((item, index) => ({
                    name: Object.keys(item)[0],
                    value: Object.values(item)[0]
                  }))}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {usersByRole.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
          </ResponsiveContainer>
          )}
        </div>

        {/* Model Run Status Distribution */}
        <div className={styles.chartCard}>
          <h3>Model Runs by Status</h3>
          {modelRunsByStatus.length > 0 && (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={modelRunsByStatus.map((item, index) => ({
                status: Object.keys(item)[0],
                count: Object.values(item)[0]
              }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="status" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" />
              </BarChart>
          </ResponsiveContainer>
          )}
        </div>

        {/* System Metrics Timeline */}
        <div className={styles.chartCard}>
          <h3>System Metrics Timeline</h3>
          {systemMetrics.length > 0 && (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={systemMetrics.map(metric => ({
                timestamp: new Date(metric.timestamp).toLocaleDateString(),
                value: metric.value,
                name: metric.name
              }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="value" stroke="#3b82f6" />
              </LineChart>
          </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className={styles.section}>
        <h2>Quick Actions</h2>
        <div className={styles.actionsGrid}>
          <button
            onClick={() => navigate('/admin/users')}
            className={styles.actionButton}
          >
            <span className={styles.actionIcon}>👥</span>
            <span>User Management</span>
          </button>
          <button
            onClick={() => navigate('/admin/tasks')}
            className={styles.actionButton}
          >
            <span className={styles.actionIcon}>📋</span>
            <span>Task Management</span>
          </button>
          <button
            onClick={() => navigate('/admin/security')}
            className={styles.actionButton}
          >
            <span className={styles.actionIcon}>🔒</span>
            <span>Security Events</span>
          </button>
          <button
            onClick={() => navigate('/admin/exports')}
            className={styles.actionButton}
          >
            <span className={styles.actionIcon}>📊</span>
            <span>Export Management</span>
          </button>
          <button
            onClick={() => navigate('/admin/custom-models')}
            className={styles.actionButton}
          >
            <span className={styles.actionIcon}>🧠</span>
            <span>Custom Models</span>
          </button>
          <button
            onClick={() => navigate('/admin/settings')}
            className={styles.actionButton}
          >
            <span className={styles.actionIcon}>⚙️</span>
            <span>System Settings</span>
          </button>
        </div>
      </div>

      {/* Recent Activity */}
      <div className={styles.section}>
        <h2>Recent Activity</h2>
        <div className={styles.activityList}>
          <div className={styles.activityItem}>
            <div className={styles.activityIcon}>👤</div>
            <div className={styles.activityContent}>
              <div className={styles.activityTitle}>New user registration</div>
              <div className={styles.activityTime}>2 minutes ago</div>
            </div>
          </div>
          <div className={styles.activityItem}>
            <div className={styles.activityIcon}>🤖</div>
            <div className={styles.activityContent}>
              <div className={styles.activityTitle}>Model training completed</div>
              <div className={styles.activityTime}>15 minutes ago</div>
            </div>
          </div>
          <div className={styles.activityItem}>
            <div className={styles.activityIcon}>📊</div>
            <div className={styles.activityContent}>
              <div className={styles.activityTitle}>Export job generated</div>
              <div className={styles.activityTime}>1 hour ago</div>
            </div>
          </div>
          <div className={styles.activityItem}>
            <div className={styles.activityIcon}>⚠️</div>
            <div className={styles.activityContent}>
              <div className={styles.activityTitle}>Suspicious login attempt detected</div>
              <div className={styles.activityTime}>2 hours ago</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;