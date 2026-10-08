import React, { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceX, forceY, forceCollide } from 'd3-force'
import { select } from 'd3-selection'
import { drag } from 'd3-drag'
import { zoom, zoomIdentity } from 'd3-zoom'

// In a real app we'd read these from CSS variables, but for D3 canvas/svg drawing we often hardcode or read computed styles.
// I'll hardcode the light theme colors that match the spec here for simplicity.
const TYPE_COLORS = {
  class: '#0F6E66', // accent
  interface: '#0F6E66',
  enum: '#0F6E66',
  record: '#0F6E66',
  method: '#2E7D4F', // ok
  constructor: '#2E7D4F',
  function: '#A86B00', // warn
}

export default function DependencyForceGraph({ nodes, edges, onNavigateToFile }) {
  const containerRef = useRef(null)
  const [hoveredNode, setHoveredNode] = useState(null)

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return

    const width = containerRef.current.clientWidth || 800
    const height = 600

    const nodeData = nodes.map((n) => ({ ...n }))
    const nodeById = new Map(nodeData.map((n) => [n.id, n]))
    const linkData = edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ ...e }))

    const svg = select(containerRef.current)
      .append('svg')
      .attr('width', '100%')
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])
      .style('display', 'block')

    svg
      .append('defs')
      .append('marker')
      .attr('id', 'dep-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#CFCDC6') // border-strong

    const g = svg.append('g')

    const zoomBehavior = zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    
    // Attach zoom but use buttons as well if we wanted (we'll stick to d3 zoom for pan/wheel)
    svg.call(zoomBehavior).on('dblclick.zoom', null)

    const fitToView = () => {
      const padding = 40
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const d of nodeData) {
        minX = Math.min(minX, d.x - 20)
        maxX = Math.max(maxX, d.x + 20 + d.label.length * 6)
        minY = Math.min(minY, d.y - 20)
        maxY = Math.max(maxY, d.y + 20)
      }
      if (minX === Infinity) return
      
      const boxW = maxX - minX
      const boxH = maxY - minY
      const scale = Math.min((width - 2 * padding) / boxW, (height - 2 * padding) / boxH, 1.2)
      const tx = (width - boxW * scale) / 2 - minX * scale
      const ty = (height - boxH * scale) / 2 - minY * scale
      
      svg.transition().duration(500).call(zoomBehavior.transform, zoomIdentity.translate(tx, ty).scale(scale))
    }

    const link = g
      .append('g')
      .attr('stroke', '#E3E2DD') // border
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
      .attr('fill', (d) => TYPE_COLORS[d.type] || '#5E6470')
      .attr('stroke', (d) => (d.has_docstring ? '#2E7D4F' : '#B42318'))
      .attr('stroke-width', 2)

    node
      .append('text')
      .text((d) => d.label)
      .attr('x', 14)
      .attr('y', 4)
      .attr('fill', '#16181D') // text
      .attr('font-size', '11px')
      .attr('font-family', '"IBM Plex Mono", monospace')
      .attr('font-weight', 500)
      .style('pointer-events', 'none')

    const paint = () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)
      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    }

    const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const simulation = forceSimulation(nodeData)
      .force('link', forceLink(linkData).id((d) => d.id).distance(80))
      .force('charge', forceManyBody().strength(-200))
      .force('x', forceX(width / 2).strength(0.05))
      .force('y', forceY(height / 2).strength(0.05))
      .force('collide', forceCollide((d) => 16 + d.label.length * 3))
      .stop()

    if (isReducedMotion) {
      simulation.tick(300)
      paint()
      fitToView()
    } else {
      simulation.tick(150)
      paint()
      fitToView()
      
      // Let it settle then stop completely
      let ticks = 0
      simulation.on('tick', () => {
        paint()
        ticks++
        if (ticks > 150) simulation.stop()
      })
      simulation.restart()
    }

    node.call(
      drag()
        .on('start', (event, d) => {
          if (!event.active && !isReducedMotion) simulation.alphaTarget(0.1).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
          if (isReducedMotion) paint()
        })
        .on('end', (event, d) => {
          if (!event.active && !isReducedMotion) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )

    node.on('mouseenter', (event, d) => setHoveredNode(d))
    node.on('mouseleave', () => setHoveredNode(null))
    node.on('click', (event, d) => {
      if (onNavigateToFile) onNavigateToFile(d.file)
    })

    // Expose fit to window buttons
    select(containerRef.current).select('.fit-btn').on('click', fitToView)

    return () => {
      simulation.stop()
      select(containerRef.current).select('svg').remove()
    }
  }, [nodes, edges, onNavigateToFile])

  return (
    <div style={{ position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '600px', cursor: 'grab' }} />
      
      <div className="graph-controls">
        <button className="secondary fit-btn" style={{ padding: '0 8px', fontSize: '0.75rem' }}>Fit to view</button>
      </div>

      {hoveredNode && (
        <div style={{ 
          position: 'absolute', 
          top: 16, 
          left: 16, 
          backgroundColor: 'var(--surface)', 
          padding: '12px', 
          border: '1px solid var(--border)',
          borderRadius: '6px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          pointerEvents: 'none'
        }}>
          <div style={{ fontFamily: '"IBM Plex Mono", monospace', fontWeight: 600, marginBottom: '4px' }}>
            {hoveredNode.label}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Type: {hoveredNode.type}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            File: {hoveredNode.file}
          </div>
          <div style={{ fontSize: '0.75rem', color: hoveredNode.has_docstring ? 'var(--ok)' : 'var(--err)', marginTop: '4px', fontWeight: 500 }}>
            {hoveredNode.has_docstring ? 'Documented' : 'Needs documentation'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', marginTop: '8px' }}>
            Click to view in changes
          </div>
        </div>
      )}
    </div>
  )
}
