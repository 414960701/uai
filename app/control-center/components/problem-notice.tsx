import { OctagonAlert } from "lucide-react";

import { ApiProblem, problemMessage } from "../api";

export function ProblemNotice({ problem }: { problem: unknown }) {
  if (!problem) return null;
  const apiProblem = problem instanceof ApiProblem ? problem.problem : undefined;
  return (
    <div className="form-error" role="alert">
      <OctagonAlert size={16} />
      <span>
        {problemMessage(problem)}
        {apiProblem?.code && <small className="problem-code">{apiProblem.code}</small>}
        {apiProblem?.field_errors?.length ? (
          <span className="problem-fields">
            {apiProblem.field_errors.map((field) => (
              <span key={`${field.field}:${field.code}`}>{field.field}：{field.message}</span>
            ))}
          </span>
        ) : null}
      </span>
    </div>
  );
}
