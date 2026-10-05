import { useEffect, useRef } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceX, forceY, forceCollide } from 'd3-force'
import { select } from 'd3-selection'
import { drag } from 'd3-drag'
import { zoom, zoomIdentity } from 'd3-zoom'

const TYPE_COLORS = {
  class: '#0366d6',
  interface: '#0366d6',
  enum: '#0366d6',
  record: '#0366d6',
  method: '#28a745',
  constructor: '#28a745',
  function: '#d9a400',
}

export default function DependencyForceGraph({ nodes, edges }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return

    const width = containerRef.current.clientWidth || 800
    const height = 500

    // d3-force mutates node/link objects in place (adds x/y/vx/vy, and
    // replaces link.source/target ids with node object references) -
    // work on copies so the React props stay untouched.
    const nodeData = nodes.map((n) => ({ ...n }))
    const nodeById = new Map(nodeData.map((n) => [n.id, n]))
    const linkData = edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ ...e }))

    const svg = select(containerRef.current)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])

    svg
      .append('defs')
      .append('marker')
      .attr('id', 'dep-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 18)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#6a737d')

    const g = svg.append('g')

    const zoomBehavior = zoom()
      .scaleExtent([0.2, 4])
      .filter((event) => (event.type === 'wheel' ? event.ctrlKey : !event.ctrlKey) && !event.button)
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    svg.call(zoomBehavior).on('dblclick.zoom', null)

    // Scale and center the whole graph (labels included) inside the box.
    const fitToView = () => {
      const padding = 28
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const d of nodeData) {
        minX = Math.min(minX, d.x - 10)
        maxX = Math.max(maxX, d.x + 14 + d.label.length * 6.6)
        minY = Math.min(minY, d.y - 10)
        maxY = Math.max(maxY, d.y + 10)
      }
      const boxW = maxX - minX
      const boxH = maxY - minY
      const scale = Math.min((width - 2 * padding) / boxW, (height - 2 * padding) / boxH, 1.3)
      const tx = (width - boxW * scale) / 2 - minX * scale
      const ty = (height - boxH * scale) / 2 - minY * scale
      svg.call(zoomBehavior.transform, zoomIdentity.translate(tx, ty).scale(scale))
    }
    svg.on('dblclick', fitToView)

    const link = g
      .append('g')
      .attr('stroke', '#b1b8c0')
      .attr('stroke-width', 1.5)
      .selectAll('line')
      .data(linkData)
      .join('line')
      .attr('marker-end', 'url(#dep-arrow)')

    const node = g
      .append('g')
      .selectAll('g')
      .data(nodeData)
      .join('g')
      .style('cursor', 'grab')

    node.append('circle')
      .attr('r', 8)
      .attr('fill', (d) => TYPE_COLORS[d.type] || '#959da5')
      .attr('stroke', (d) => (d.has_docstring ? '#28a745' : '#cb2431'))
      .attr('stroke-width', 2)

    node.append('title').text((d) => d.id)

    node
      .append('text')
      .text((d) => d.label)
      .attr('x', 12)
      .attr('y', 4)
      .attr('fill', '#24292e')
      .attr('font-size', '11px')
      .attr('font-family', 'monospace')

    const paint = () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)
      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    }

    // forceX/forceY keep disconnected clusters near the middle instead of drifting apart.
    const simulation = forceSimulation(nodeData)
      .force('link', forceLink(linkData).id((d) => d.id).distance(100))
      .force('charge', forceManyBody().strength(-320))
      .force('x', forceX(width / 2).strength(0.03))
      .force('y', forceY(height / 2).strength(0.2))
      .force('collide', forceCollide((d) => 16 + d.label.length * 3.4))
      .stop()

    // Settle the layout before the first paint so the graph appears already fitted.
    simulation.tick(300)
    paint()
    fitToView()
    simulation.on('tick', paint)

    node.call(
      drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )

    return () => {
      simulation.stop()
      select(containerRef.current).selectAll('*').remove()
    }
  }, [nodes, edges])

  return <div className="graph-canvas" ref={containerRef} />
}
