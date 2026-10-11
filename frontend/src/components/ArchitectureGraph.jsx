import React, { useMemo, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
} from 'reactflow';
import dagre from 'dagre';
import { FileCode, Globe, ArrowDownRight, ArrowUpRight } from 'lucide-react';

// Curated folder color themes
const FOLDER_COLORS = [
  { border: 'border-indigo-500/80', bg: 'bg-indigo-950/40', text: 'text-indigo-300', badge: 'bg-indigo-500/20' },
  { border: 'border-emerald-500/80', bg: 'bg-emerald-950/40', text: 'text-emerald-300', badge: 'bg-emerald-500/20' },
  { border: 'border-amber-500/80', bg: 'bg-amber-950/40', text: 'text-amber-300', badge: 'bg-amber-500/20' },
  { border: 'border-cyan-500/80', bg: 'bg-cyan-950/40', text: 'text-cyan-300', badge: 'bg-cyan-500/20' },
  { border: 'border-purple-500/80', bg: 'bg-purple-950/40', text: 'text-purple-300', badge: 'bg-purple-500/20' },
  { border: 'border-rose-500/80', bg: 'bg-rose-950/40', text: 'text-rose-300', badge: 'bg-rose-500/20' },
  { border: 'border-teal-500/80', bg: 'bg-teal-950/40', text: 'text-teal-300', badge: 'bg-teal-500/20' },
];

function getFolderTheme(path, isExternal) {
  if (isExternal) {
    return {
      border: 'border-slate-600',
      bg: 'bg-slate-900/90',
      text: 'text-slate-400',
      badge: 'bg-slate-800',
    };
  }
  if (!path || !path.includes('/')) {
    return FOLDER_COLORS[0]; // root files
  }
  const folder = path.split('/')[0];
  let hash = 0;
  for (let i = 0; i < folder.length; i++) {
    hash = (hash << 5) - hash + folder.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % FOLDER_COLORS.length;
  return FOLDER_COLORS[index];
}

// Custom Node Component
const CustomFileNode = ({ data = {}, selected }) => {
  if (!data) return null;
  const theme = getFolderTheme(data.path, data.is_external);
  const isHighlighted = data.isHighlighted;
  const isDimmed = data.isDimmed;

  return (
    <div
      className={`px-4 py-3 rounded-2xl border-2 transition-all duration-200 cursor-pointer min-w-[210px] shadow-lg ${
        theme.bg
      } ${theme.border} ${
        selected ? 'ring-4 ring-brand-400 shadow-brand-500/30 scale-105' : ''
      } ${isHighlighted ? 'ring-2 ring-amber-400 scale-105' : ''} ${
        isDimmed ? 'opacity-30' : 'opacity-100'
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-400 !w-2.5 !h-2.5" />

      <div className="flex items-center space-x-2.5 mb-1.5">
        <div className={`p-1.5 rounded-lg ${theme.badge}`}>
          {data.is_external ? (
            <Globe className="h-4 w-4 text-slate-400" />
          ) : (
            <FileCode className={`h-4 w-4 ${theme.text}`} />
          )}
        </div>
        <div className="truncate">
          <p className="text-xs font-bold text-white truncate max-w-[140px]">{data.label || 'file'}</p>
          <p className="text-[10px] text-slate-400 truncate max-w-[140px] font-mono">
            {data.path || 'external'}
          </p>
        </div>
      </div>

      {/* Degree & Line Count Badges */}
      <div className="flex items-center justify-between text-[10px] pt-2 border-t border-slate-700/60 text-slate-400">
        <div className="flex items-center space-x-2">
          <span className="flex items-center space-x-0.5" title="In-degree (times imported)">
            <ArrowDownRight className="h-3 w-3 text-emerald-400" />
            <strong className="text-slate-200">{data.in_degree || 0}</strong>
          </span>
          <span className="flex items-center space-x-0.5" title="Out-degree (imports count)">
            <ArrowUpRight className="h-3 w-3 text-indigo-400" />
            <strong className="text-slate-200">{data.out_degree || 0}</strong>
          </span>
        </div>
        {!data.is_external && (data.line_count || 0) > 0 && (
          <span className="font-mono text-slate-400">{data.line_count}L</span>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-400 !w-2.5 !h-2.5" />
    </div>
  );
};

// Define nodeTypes outside of component to prevent re-creation warnings
const nodeTypes = {
  customFileNode: CustomFileNode,
};

// Dagre Layout Engine
function getLayoutedElements(nodes, edges, direction = 'TB') {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 40,
    ranksep: 70,
    marginx: 20,
    marginy: 20,
  });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 230, height: 95 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: (nodeWithPosition?.x || 0) - 115,
        y: (nodeWithPosition?.y || 0) - 47.5,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

export default function ArchitectureGraph({
  graphData,
  searchQuery,
  onNodeClick,
  selectedNodeId,
}) {
  // Convert API graph data into React Flow nodes and edges
  const { initialNodes, initialEdges } = useMemo(() => {
    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
      return { initialNodes: [], initialEdges: [] };
    }

    const flowNodes = graphData.nodes.map((n) => {
      const isMatch = searchQuery && n.label.toLowerCase().includes(searchQuery.toLowerCase());
      const isDimmed = searchQuery && !isMatch;

      return {
        id: n.id,
        type: 'customFileNode',
        data: {
          ...n,
          isHighlighted: isMatch,
          isDimmed: isDimmed,
        },
        position: { x: 0, y: 0 },
      };
    });

    const flowEdges = (graphData.edges || []).map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      animated: e.is_external === false,
      style: {
        stroke: e.is_external ? '#64748b' : '#818cf8',
        strokeWidth: e.is_external ? 1.5 : 2,
        strokeDasharray: e.is_external ? '4,4' : undefined,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: e.is_external ? '#64748b' : '#818cf8',
        width: 14,
        height: 14,
      },
      data: {
        symbols: e.imported_symbols,
        line_number: e.line_number,
      },
    }));

    // getLayoutedElements returns { nodes, edges } -> map to { initialNodes, initialEdges }
    const layout = getLayoutedElements(flowNodes, flowEdges, 'TB');
    return {
      initialNodes: layout.nodes,
      initialEdges: layout.edges,
    };
  }, [graphData, searchQuery]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync state whenever layout changes
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (event, node) => {
      if (node && node.data) {
        onNodeClick(node.data);
      }
    },
    [onNodeClick]
  );

  return (
    <div className="w-full h-full relative" style={{ minHeight: '500px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2.5}
      >
        <Background color="#334155" gap={20} size={1} />
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          nodeColor={(node) => (node.data?.is_external ? '#64748b' : '#818cf8')}
          maskColor="rgba(15, 23, 42, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}
