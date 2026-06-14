def make_xml(cells, title='Diagram'):
    body = '\n'.join(cells)
    return (
        '<mxfile>\n'
        f'  <diagram name="{title}">\n'
        '    <mxGraphModel>\n'
        '      <root>\n'
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        f'{body}\n'
        '      </root>\n'
        '    </mxGraphModel>\n'
        '  </diagram>\n'
        '</mxfile>\n'
    )
