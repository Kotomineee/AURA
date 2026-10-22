"""Group verified executable identities without exposing paths or guessing owners."""
import re


def key(row):
    opaque=row.get('icon_id')
    if isinstance(opaque,str) and re.fullmatch('[0-9a-f]{64}',opaque):
        return opaque+':'+row['name'].casefold()
    # Without a verified executable identity, keep this process independent.
    return f"pid:{row['pid']}:{row['created_at']}"


def members(row):return row.get('members',[row])


def group(rows):
    buckets={};seen=set()
    for entry in rows:
        for row in members(entry):
            identity=(row['pid'],row['created_at'])
            if identity in seen:continue
            seen.add(identity)
            buckets.setdefault(key(row),[]).append(row)
    result=[]
    for identity,children in buckets.items():
        children.sort(key=lambda r:(r['created_at'],r['pid']))
        result.append(dict(children[0],group_id=identity,members=children,
                           process_count=len(children),ram_mb=round(sum(r['ram_mb'] for r in children),1)))
    return sorted(result,key=lambda r:(-r['ram_mb'],r['name'].casefold()))


def contains(row,term):
    return term.casefold() in row['name'].casefold() or any(term in str(child['pid']) for child in members(row))


def terminate_snapshot(row,send):
    """The server rechecks name, PID, birth time and protection for every member."""
    sent=0;failed=0;messages=[]
    for child in reversed(members(row)):
        try:
            result=send({field:child[field] for field in ('pid','name','created_at')})
            sent+=1;messages.append(result.get('message',''))
        except (OSError,RuntimeError):failed+=1
    simulation=bool(messages) and all(message.startswith('SIMULAÇÃO:') for message in messages)
    prefix='Simulação: ' if simulation else ''
    return {'message':prefix+f'{sent} de {sent+failed} solicitações concluídas.'+(' Alguns processos já encerraram ou não puderam ser alterados; atualize a lista.' if failed else ''),
            'sent':sent,'failed':failed}
