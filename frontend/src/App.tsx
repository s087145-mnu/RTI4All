import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { AppShell } from "@/components/Layout";
import { RequireAdmin, RequireAuth } from "@/components/RouteGuards";

import { HomePage } from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { SignupPage } from "@/pages/SignupPage";
import { RequestsPage } from "@/pages/RequestsPage";
import { NewRequestPage } from "@/pages/NewRequestPage";
import { RequestDetailPage } from "@/pages/RequestDetailPage";
import { DepartmentsPage } from "@/pages/DepartmentsPage";
import { FaqsPage } from "@/pages/FaqsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { AdminInboxPage } from "@/pages/admin/AdminInboxPage";
import { AdminReviewPage } from "@/pages/admin/AdminReviewPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />

            <Route
              path="/requests"
              element={
                <RequireAuth>
                  <RequestsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/requests/new"
              element={
                <RequireAuth>
                  <NewRequestPage />
                </RequireAuth>
              }
            />
            <Route
              path="/requests/:id"
              element={
                <RequireAuth>
                  <RequestDetailPage />
                </RequireAuth>
              }
            />

            <Route path="/departments" element={<DepartmentsPage />} />
            <Route path="/faqs" element={<FaqsPage />} />

            <Route
              path="/admin"
              element={
                <RequireAdmin>
                  <AdminInboxPage />
                </RequireAdmin>
              }
            />
            <Route
              path="/admin/requests/:id"
              element={
                <RequireAdmin>
                  <AdminReviewPage />
                </RequireAdmin>
              }
            />

            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
