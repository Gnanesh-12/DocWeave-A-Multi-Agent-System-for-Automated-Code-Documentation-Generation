import { useEffect, useRef } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import { select } from 'd3-selection'
import { drag } from 'd3-drag'
import { zoom } from 'd3-zoom'

const TYPE_COLORS = {
  class: '#4f7cff',
  method: '#7ee2a8',
  function: '#e8c46a',
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
      .attr('fill', '#4a5468')

    const g = svg.append('g')

    svg.call(
      zoom()
        .scaleExtent([0.2, 4])
        .on('zoom', (event) => {
          g.attr('transform', event.transform)
        })
    )

    const link = g
      .append('g')
      .attr('stroke', '#2d3340')
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
      .attr('fill', (d) => TYPE_COLORS[d.type] || '#9aa0a6')
      .attr('stroke', (d) => (d.has_docstring ? '#7ee2a8' : '#ff9b93'))
      .attr('stroke-width', 2)

    node.append('title').text((d) => d.id)

    node
      .append('text')
      .text((d) => d.label)
      .attr('x', 12)
      .attr('y', 4)
      .attr('fill', '#cdd8ff')
      .attr('font-size', '11px')
      .attr('font-family', 'monospace')

    const simulation = forceSimulation(nodeData)
      .force('link', forceLink(linkData).id((d) => d.id).distance(80))
      .force('charge', forceManyBody().strength(-220))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide(32))
      .on('tick', () => {
        link
          .attr('x1', (d) => d.source.x)
          .attr('y1', (d) => d.source.y)
          .attr('x2', (d) => d.target.x)
          .attr('y2', (d) => d.target.y)
        node.attr('transform', (d) => `translate(${d.x},${d.y})`)
      })

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
