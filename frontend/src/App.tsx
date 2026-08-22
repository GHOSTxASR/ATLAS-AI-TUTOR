import { Outlet } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";

export function App() {
  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
}

