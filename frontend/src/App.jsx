// frontend/src/App.jsx
import React, { Suspense, lazy, useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import useAuthStore from './lib/auth';

// --- Layouts ---
import Layout from './components/Layout';
import Spinner from './components/Spinner';

// --- Page Components ---
const Home = lazy(() => import('./pages/Home'));
const Login = lazy(() => import('./pages/Login'));
const Signup = lazy(() => import('./pages/Signup'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const NewTask = lazy(() => import('./pages/NewTask'));
const ModelSelection = lazy(() => import('./pages/ModelSelection'));
const UploadData = lazy(() => import('./pages/UploadData'));
const AnalyzeData = lazy(() => import('./pages/AnalyzeData'));
const CleanData = lazy(() => import('./pages/CleanData'));
const ConfigureTrain = lazy(() => import('./pages/ConfigureTrain'));
const Training = lazy(() => import('./pages/Training'));
const Results = lazy(() => import('./pages/Results'));

// Loading component
const LoadingScreen = () => (
    <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        backgroundColor: '#f8fafc'
    }}>
        <div style={{ textAlign: 'center' }}>
            <Spinner size="large" />
            <p style={{ marginTop: '1rem', color: '#64748b' }}>Loading...</p>
        </div>
    </div>
);

function ProtectedRoute({ children }) {
    const { isAuthenticated, isLoading } = useAuthStore();

    if (isLoading) {
        return <LoadingScreen />;
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return children;
}

function PublicRoute({ children }) {
    const { isAuthenticated, isLoading } = useAuthStore();

    if (isLoading) {
        return <LoadingScreen />;
    }

    if (isAuthenticated) {
        return <Navigate to="/dashboard" replace />;
    }

    return children;
}

function App() {
    const { initializeAuth, isLoading } = useAuthStore();

    useEffect(() => {
        // Initialize authentication state on app startup
        initializeAuth();
    }, [initializeAuth]);

    // Show loading screen while auth is initializing
    if (isLoading) {
        return <LoadingScreen />;
    }

    return (
        <div className="App">
                <Suspense fallback={<LoadingScreen />}>
                    <Routes>
                        {/* Public Routes */}
                        <Route
                            path="/"
                            element={
                                <PublicRoute>
                                    <Home />
                                </PublicRoute>
                            }
                        />
                        <Route
                            path="/login"
                            element={
                                <PublicRoute>
                                    <Login />
                                </PublicRoute>
                            }
                        />
                        <Route
                            path="/signup"
                            element={
                                <PublicRoute>
                                    <Signup />
                                </PublicRoute>
                            }
                        />

                        {/* Protected Routes */}
                        <Route
                            path="/dashboard"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <Dashboard />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/task/new"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <NewTask />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/task/:taskId/select-model"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <ModelSelection />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/task/:taskId/model/:modelId/upload"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <UploadData />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/run/:runId/analyze"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <AnalyzeData />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/run/:runId/clean"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <CleanData />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/run/:runId/configure"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <ConfigureTrain />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/run/:runId/training"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <Training />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/run/:runId/results"
                            element={
                                <ProtectedRoute>
                                    <Layout>
                                        <Results />
                                    </Layout>
                                </ProtectedRoute>
                            }
                        />

                        {/* Fallback */}
                        <Route path="*" element={<Navigate to="/dashboard" replace />} />
                    </Routes>
                </Suspense>
            </div>
        // </Router>
    );
}

export default App;