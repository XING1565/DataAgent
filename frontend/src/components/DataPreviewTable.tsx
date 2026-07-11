type Props = {
  rows: Record<string, unknown>[];
  compact?: boolean;
};

export function DataPreviewTable({ rows, compact = false }: Props) {
  if (!rows.length) {
    return <div className="empty-state">暂无可展示数据</div>;
  }

  const columns = Object.keys(rows[0]);

  return (
    <div className="table-wrap">
      <table className={compact ? "data-table compact" : "data-table"}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{formatCell(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return "空值";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
