import { useLocation, useNavigate } from "react-router-dom";
import { Tabs } from "../ui";

const ITEMS = [
  { value: "/", label: "My Agents" },
  { value: "/shared", label: "Shared With Me" },
];

export function AgentListTabs() {
  const location = useLocation();
  const navigate = useNavigate();
  const active = ITEMS.find((item) => item.value === location.pathname)?.value ?? "/";

  return <Tabs items={ITEMS} value={active} onChange={(value) => navigate(value)} />;
}
