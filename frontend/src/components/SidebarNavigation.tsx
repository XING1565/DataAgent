import { BarChart3, Bot, Database, FileText, LayoutDashboard, Settings } from "lucide-react";

export type AppSection = "workspace" | "dashboard" | "collection" | "analysis" | "reports" | "settings";

type Props = {
  activeSection: AppSection;
  onChange: (section: AppSection) => void;
};

const NAV_ITEMS: Array<{ key: AppSection; label: string; icon: typeof LayoutDashboard }> = [
  { key: "workspace", label: "工作台", icon: LayoutDashboard },
  { key: "dashboard", label: "数据看板", icon: BarChart3 },
  { key: "collection", label: "数据采集", icon: Database },
  { key: "analysis", label: "智能分析", icon: Bot },
  { key: "reports", label: "报表中心", icon: FileText },
  { key: "settings", label: "设置", icon: Settings },
];

export function SidebarNavigation({ activeSection, onChange }: Props) {
  return (
    <nav className="module-nav" aria-label="工作台模块">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <button
            className={activeSection === item.key ? "active" : ""}
            key={item.key}
            onClick={() => onChange(item.key)}
            type="button"
          >
            <Icon size={15} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
