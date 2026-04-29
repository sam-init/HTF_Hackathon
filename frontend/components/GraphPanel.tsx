import { GraphPayload } from "@/lib/types";

type Props = {
  title: string;
  graph: GraphPayload;
};

export function GraphPanel({ title, graph }: Props) {
  const nodes = graph.nodes.slice(0, 24);
  const edges = graph.edges.slice(0, 28);
  const width = 780;
  const height = 320;

  const positioned = nodes.map((node, idx) => {
    const col = idx % 6;
    const row = Math.floor(idx / 6);
    return {
      ...node,
      x: 90 + col * 120,
      y: 45 + row * 72,
    };
  });

  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <svg width={width} height={height} style={{ background: "#f8fbfd", borderRadius: 12 }}>
        {edges.map((edge, idx) => {
          const source = positioned.find((n) => n.id === edge.source);
          const target = positioned.find((n) => n.id === edge.target);
          if (!source || !target) return null;
          return (
            <line
              key={`${edge.source}-${edge.target}-${idx}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="#9ab4c8"
              strokeWidth="1.2"
            />
          );
        })}

        {positioned.map((node) => (
          <g key={node.id}>
            <circle cx={node.x} cy={node.y} r={15} fill="#007ea7" opacity="0.85" />
            <text x={node.x + 20} y={node.y + 5} fontSize="11" fill="#163248">
              {node.label.slice(0, 20)}
            </text>
          </g>
        ))}
      </svg>
      <p style={{ color: "var(--muted)", marginBottom: 0 }}>Showing sampled nodes for readability.</p>
    </div>
  );
}
