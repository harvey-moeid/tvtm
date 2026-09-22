from __future__ import annotations
import logging,sys
from datetime import datetime,timezone
from src.config_loader import load_strategy_config,load_symbols,require_env
from src.storage.d1_client import D1Client
from src.strategy.strategy import MarketDataUnavailable,dispatch_signal,evaluate_market
logging.basicConfig(level=logging.INFO,format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
def main()->int:
 started=datetime.now(timezone.utc)
 try:webhook=require_env('DISCORD_WEBHOOK_URL');account=require_env('CF_ACCOUNT_ID');dbid=require_env('CF_D1_DATABASE_ID');token=require_env('CF_API_TOKEN')
 except RuntimeError as e:logging.error('Konfigurasi environment tidak lengkap: %s',e);return 1
 d1=D1Client(account,dbid,token);summary={'evaluated':0,'skipped':0,'signals':0,'notified':0,'errors':0,'data_errors':0}
 for cfg in load_symbols():
  if not cfg.get('enabled',True):continue
  summary['evaluated']+=1
  try:
   signal=evaluate_market(cfg,load_strategy_config(cfg['symbol']),d1,webhook)
   if signal is None:summary['skipped']+=1;continue
   summary['signals']+=1
   if dispatch_signal(webhook,d1,signal):summary['notified']+=1
  except MarketDataUnavailable as e:summary['data_errors']+=1;logging.error('[%s] %s',cfg['id'],e)
  except Exception:summary['errors']+=1;logging.exception('[%s] error',cfg['id'])
 logging.info('run %.2fs evaluated=%d skipped=%d signals=%d notified=%d errors=%d data_errors=%d',(datetime.now(timezone.utc)-started).total_seconds(),summary['evaluated'],summary['skipped'],summary['signals'],summary['notified'],summary['errors'],summary['data_errors'])
 return 1 if summary['evaluated'] and summary['data_errors']==summary['evaluated'] else 0
if __name__=='__main__':sys.exit(main())