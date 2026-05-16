'use client'
import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

/**
 * ShadowTrace AI — GraphView
 * Robust visualization for investigation entities and relationships.
 * Uses only default node types to prevent "Node type not found" crashes.
 */

function getNodeStyle(type: string, risk: string) {
  const bg: Record<string, string> = {
    company: '#3b82f6',  // Blue
    person: '#22c55e',   // Green
    domain: '#eab308',   // Yellow
    address: '#f97316',  // Orange
    social: '#a855f7'    // Purple
  }
  const border = risk === 'HIGH' ? '3px solid #ef4444'
    : risk === 'MEDIUM' ? '3px solid #f97316' : '2px solid #22c55e'
  
  return {
    background: bg[type.toLowerCase()] ?? '#6b7280',
    border,
    borderRadius: 8,
    color: '#fff',
    padding: '8px 12px',
    fontSize: 12,
    minWidth: 100,
    fontWeight: 500,
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
  }
}

export default function GraphView({ report }: { report: any }) {
  // Ensure we extract from all possible report shapes (entities or graph.nodes)
  const entities = report?.entities ?? report?.graph?.nodes ?? []
  const relationships = report?.relationships ?? report?.graph?.edges ?? []

  const nodes = entities.map((e: any, i: number) => ({
    id: String(e.id ?? i),
    type: 'default',   // ALWAYS use default type
    position: { x: (i % 4) * 220, y: Math.floor(i / 4) * 160 },
    data: { label: e.name ?? e.label ?? e.id ?? 'Unknown' },
    style: getNodeStyle(e.type ?? 'company', e.risk ?? 'LOW')
  }))

  const edges = relationships.map((r: any, i: number) => ({
    id: `e${i}`,
    source: String(r.source),
    target: String(r.target),
    label: r.type ?? r.label ?? '',
    type: 'default',
    animated: true,
    style: { stroke: '#475569' }
  }))

  if (nodes.length === 0) return (
    <div style={{ color: '#888', textAlign: 'center', padding: 40 }}>
      No graph data available for this investigation.
    </div>
  )

  return (
    <div style={{ width: '100%', height: '100%', minHeight: 450 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable
        nodesConnectable={false}
        colorMode="dark"
      >
        <Background gap={12} color="#334155" />
        <Controls />
        <MiniMap 
          nodeColor={(n) => (n.style?.background as string) || '#ccc'} 
          maskColor="rgba(0,0,0,0.1)"
          style={{ background: '#0f172a' }}
        />
      </ReactFlow>
    </div>
  )
}
