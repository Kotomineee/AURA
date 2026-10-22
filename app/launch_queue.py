"""Authenticated opaque requests. The privileged agent never executes targets."""
import threading
import time
import uuid


class LaunchQueue:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.lock=threading.RLock();self.rows={};self.jobs={};self.owner='';self.heartbeat=-100.;self.catalog_at=-100.;self.refresh_requested=False
    def online(self):return self.clock()-self.heartbeat<8
    def worker(self,owner,rows=None,results=()):
        with self.lock:
            now=self.clock()
            if self.online() and self.owner!=owner:raise ValueError('Outra janela da AURA já está atendendo a abertura de aplicativos.')
            self.owner=owner;self.heartbeat=now
            if rows is not None:self.rows={r['id']:r for r in rows};self.catalog_at=now
            self.expire()
            for result in results:
                job=self.jobs.get(result['request_id'])
                if job and job['state']=='dispatch' and job['owner']==owner:
                    job.update(state='opened' if result['ok'] else 'failed',message=result['message'][:240])
            for job in self.jobs.values():
                if job['state']=='pending':
                    if job['app_id'] not in self.rows:job.update(state='failed',message='Aplicativo removido. Atualize a lista.');continue
                    job.update(state='dispatch',owner=owner)
                    return {'request_id':job['request_id'],'app_id':job['app_id'],'expires_at':job['created']+20}
            return None
    def expire(self):
        now=self.clock()
        for key,job in list(self.jobs.items()):
            if now-job['created']>90:del self.jobs[key]
            elif job['state'] in ('pending','dispatch') and now-job['created']>20:job.update(state='failed',message='A solicitação expirou. Confira a AURA no Windows e tente novamente.')
    def catalog(self):
        with self.lock:
            if not self.online():raise ValueError('Abra a AURA no Windows ou mantenha-a na bandeja para abrir aplicativos.')
            return list(self.rows.values())
    def request(self,command_id,key):
        uuid.UUID(command_id)
        with self.lock:
            self.expire()
            if command_id in self.jobs:
                job=self.jobs[command_id]
                if job['app_id']!=key:raise ValueError('Identificador de solicitação já utilizado.')
                return self.status(command_id)
            if not self.online():raise ValueError('A AURA no Windows está desconectada. Abra o aplicativo no PC.')
            if key not in self.rows:raise KeyError('Aplicativo não encontrado. Atualize a lista no Windows.')
            if len(self.jobs)>=128:raise ValueError('Muitas solicitações. Aguarde um momento.')
            self.jobs[command_id]={'request_id':command_id,'app_id':key,'state':'pending','message':'Aguardando o Windows…','created':self.clock(),'owner':''}
            return self.status(command_id)
    def status(self,key):
        with self.lock:
            self.expire()
            job=self.jobs[key]
            return {k:job[k] for k in ('request_id','state','message')}
