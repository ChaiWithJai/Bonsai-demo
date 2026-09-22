"""Read slide text and tables in presentation order, without fetching relationships."""
import io
import posixpath
import zipfile
from xml.etree import ElementTree as ET

P='{http://schemas.openxmlformats.org/presentationml/2006/main}'
A='{http://schemas.openxmlformats.org/drawingml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL='{http://schemas.openxmlformats.org/package/2006/relationships}'


def extract_pptx(content,max_rows):
    records=[];slides=[]
    def paragraph(node):
        return ''.join((el.text or '') if el.tag==A+'t' else '\n' if el.tag==A+'br' else '\t' if el.tag==A+'tab' else '' for el in node.iter())
    def append(locator,data):
        records.append({'locator':locator,'data':data})
        if len(records)>max_rows:raise ValueError('Presentation exceeds record limits')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos=archive.infolist();names=[item.filename for item in infos]
            if len(names)!=len(set(names)) or len(infos)>5000 or sum(item.file_size for item in infos)>100*1024*1024:
                raise ValueError('Presentation exceeds archive limits or contains duplicate parts')
            def xml(name):
                raw=archive.read(name)
                if len(raw)>20*1024*1024 or b'<!DOCTYPE' in raw.replace(b'\x00',b'').upper() or b'<!ENTITY' in raw.replace(b'\x00',b'').upper():
                    raise ValueError('Presentation XML exceeds supported limits')
                return ET.fromstring(raw)
            presentation=xml('ppt/presentation.xml')
            rels={}
            for rel in xml('ppt/_rels/presentation.xml.rels').findall(REL+'Relationship'):
                rid=rel.get('Id')
                if rid in rels:raise ValueError('Presentation has ambiguous relationships')
                rels[rid]=rel
            for ordinal,ref in enumerate(presentation.findall('./'+P+'sldIdLst/'+P+'sldId'),1):
                rel=rels.get(ref.get(R+'id'))
                if rel is None or rel.get('TargetMode')=='External' or not rel.get('Type','').endswith('/slide'):
                    raise ValueError('Presentation slide relationship is missing or unsupported')
                target=rel.get('Target','')
                part=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt',target))
                if '\\' in target or not part.startswith('ppt/slides/') or not part.endswith('.xml'):
                    raise ValueError('Presentation slide target is outside supported parts')
                slide=xml(part);hidden=slide.get('show')=='0';before=len(records)
                tree=slide.find('./'+P+'cSld/'+P+'spTree')
                if tree is not None:
                    for shape_index,shape in enumerate(tree.iter(),1):
                        base={'slide':ordinal,'slide_part':part,'shape':shape_index,'hidden_slide':hidden}
                        if shape.tag==P+'sp':
                            for paragraph_index,node in enumerate(shape.findall('./'+P+'txBody/'+A+'p'),1):
                                value=paragraph(node)
                                if value.strip():append({**base,'paragraph':paragraph_index},{'text':value})
                        elif shape.tag==A+'tbl':
                            for row_index,row in enumerate(shape.findall(A+'tr'),1):
                                cells=['\n'.join(paragraph(p) for p in cell.findall('./'+A+'txBody/'+A+'p')) for cell in row.findall(A+'tc')]
                                if any(cell.strip() for cell in cells):append({**base,'table_row':row_index},{'cells':cells})
                slides.append({'slide':ordinal,'part':part,'hidden':hidden,'records':len(records)-before})
            media=sum(name.startswith('ppt/media/') and not name.endswith('/') for name in names)
            notes=[name for name in names if name.startswith('ppt/notesSlides/notesSlide') and name.endswith('.xml')]
    except (zipfile.BadZipFile,KeyError,ET.ParseError) as exc:
        raise ValueError('Could not read presentation slide text') from exc
    if not records:raise ValueError('No readable slide text or table cells; image-only presentations require visual extraction')
    return {'kind':'presentation','status':'extracted','extractor':'pptx-slide-xml-v1','requires_structuring':True,'records':records,
            'document_coverage':{'scope':'Slide text and table cells in presentation order; hidden slides identified in source locations',
              'slides':slides,'embedded_media_not_read':media,'other_parts_not_read':notes,
              'limitations':'Images, charts, diagrams, speaker notes, animations, and visual layout are not interpreted. Textless slides remain listed in coverage.'}}
