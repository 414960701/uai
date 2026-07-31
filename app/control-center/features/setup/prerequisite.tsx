import { ArrowRight, OctagonAlert } from "lucide-react";

export type ReadinessIssue = {
  code: string;
  resource_type: string;
  resource_id?: string | null;
  path?: string | null;
  message: string;
  remediation: { action: string; target?: string | null };
};

export function ReadinessList({ issues, limit = 5 }: { issues: ReadinessIssue[]; limit?: number }) {
  if (!issues.length) {
    return <div className="empty-inline">请刷新控制面 SetupStatus，或检查模型连接和 Agent 修订。</div>;
  }
  return (
    <div className="readiness-issue-list">
      {issues.slice(0, limit).map((issue) => (
        <div key={`${issue.code}:${issue.resource_id || "root"}`}>
          <strong>{issue.code}</strong>
          <span>{issue.message}</span>
        </div>
      ))}
    </div>
  );
}

export function PrerequisiteGate({
  title,
  description,
  issues,
  onRepair,
}: {
  title: string;
  description: string;
  issues: ReadinessIssue[];
  onRepair: () => void;
}) {
  return (
    <div className="prerequisite-panel" role="status">
      <div className="eyebrow"><OctagonAlert size={15} /> 当前没有可运行目标</div>
      <h3>{title}</h3>
      <p>{description}</p>
      <ReadinessList issues={issues} />
      <button type="button" className="button button-secondary" onClick={onRepair}>
        打开修复入口 <ArrowRight size={15} />
      </button>
    </div>
  );
}
