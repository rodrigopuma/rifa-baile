import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { PageLoading } from "./components/Spinner";
import { CampaignProvider } from "./hooks/CampaignContext";
import { SelectionProvider } from "./hooks/SelectionContext";
import Home from "./pages/Home";
import Order from "./pages/Order";
import Participate from "./pages/Participate";
import Privacy from "./pages/Privacy";
import Receipt from "./pages/Receipt";
import Regulation from "./pages/Regulation";

const AdminApp = lazy(() => import("./pages/admin/AdminApp"));

function PublicSite() {
  return (
    <CampaignProvider>
      <SelectionProvider>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/participar" element={<Participate />} />
          <Route path="/pedido/:id" element={<Order />} />
          <Route path="/regulamento" element={<Regulation />} />
          <Route path="/privacidade" element={<Privacy />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </SelectionProvider>
    </CampaignProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}>
      <Routes>
        <Route path="/admin/*" element={<Suspense fallback={<PageLoading />}><AdminApp /></Suspense>} />
        <Route path="/comprovante/:id" element={<Receipt />} />
        <Route path="/*" element={<PublicSite />} />
      </Routes>
    </BrowserRouter>
  );
}
