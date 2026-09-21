"""Local email exports become source-bound records; nothing is sent or fetched."""
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import mailbox
from pathlib import Path
import tempfile


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if not self.hidden and tag in ('p','div','br','li','tr'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if not self.hidden and tag in ('p','div','li','tr'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def record(message,index):
    part=message.get_body(preferencelist=('plain','html'))
    body=''
    if part:
        try:body=part.get_content()
        except (LookupError,UnicodeError):
            body=(part.get_payload(decode=True) or b'').decode('utf-8',errors='replace')
        if not isinstance(body,str):body=''
        if part.get_content_type()=='text/html':
            parser=TextHTML();parser.feed(body);body='\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
    date=str(message.get('Date',''));sent_date=None
    if date:
        try:sent_date=parsedate_to_datetime(date).date().isoformat()
        except (ValueError,TypeError,OverflowError):pass
    attachments=[]
    for item in message.iter_attachments():
        payload=item.get_payload(decode=True)
        attachments.append({'filename':item.get_filename(),'content_type':item.get_content_type(),'bytes':len(payload) if payload is not None else None})
    data={key:str(message.get(header,'')) for key,header in [('from','From'),('to','To'),('cc','Cc'),('subject','Subject'),('message_id','Message-ID'),('in_reply_to','In-Reply-To'),('references','References')]}
    data.update(date_original=date,sent_date=sent_date,body=body.strip(),attachments=json.dumps(attachments,ensure_ascii=False),attachment_count=len(attachments))
    if not any(data[key] for key in ('from','to','subject','body')):
        raise ValueError(f'Email {index} has no readable headers or body')
    return {'locator':{'message':index,'message_id':data['message_id'] or None},'data':data},len(attachments)


def extract_email(name,content,max_rows):
    parser=BytesParser(policy=policy.default)
    if Path(name).suffix.lower()=='.eml':messages=[parser.parsebytes(content)]
    else:
        if not content.startswith(b'From '):raise ValueError('MBOX export must start with a From envelope line')
        with tempfile.TemporaryDirectory(prefix='bonsai-mbox-') as folder:
            path=Path(folder)/'mailbox';path.write_bytes(content)
            box=mailbox.mbox(path,factory=lambda stream:parser.parse(stream),create=False)
            try:
                if len(box)>max_rows:raise ValueError('Email export exceeds the record limit')
                messages=list(box)
            finally:box.close()
    if not 1<=len(messages)<=max_rows:raise ValueError('Email export contains no messages or exceeds the record limit')
    rows=[];attachments=0
    for i,message in enumerate(messages,1):
        row,count=record(message,i);rows.append(row);attachments+=count
    return {'kind':'email','status':'extracted','extractor':'email-export-v1','records':rows,
            'email_coverage':{'messages':len(rows),'attachments':attachments,'limitation':'Message headers and bodies are extracted locally. Attachments are listed but their contents are not extracted. Original MIME bytes are preserved.'}}
