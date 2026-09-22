export async function onRequest(context) {
  const { env, request } = context;
  const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET,OPTIONS","Content-Type":"application/json"};
  if(request.method==="OPTIONS")return new Response(null,{status:204,headers});
  if(!env.DB)return new Response(JSON.stringify({error:"D1 binding 'DB' tidak ditemukan."}),{status:500,headers});
  try{
    const [trade,signal,open] = await Promise.all([
      env.DB.prepare("SELECT COUNT(*) total, SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) closed, SUM(CASE WHEN status='CLOSED' AND pnl_r>0 THEN 1 ELSE 0 END) wins, COALESCE(SUM(CASE WHEN status='CLOSED' THEN pnl_pct ELSE 0 END),0) pnl_pct, COALESCE(SUM(CASE WHEN status='CLOSED' THEN pnl_r ELSE 0 END),0) pnl_r FROM trades").first(),
      env.DB.prepare("SELECT COUNT(*) total, SUM(CASE WHEN direction='BUY' THEN 1 ELSE 0 END) buys, SUM(CASE WHEN direction='SELL' THEN 1 ELSE 0 END) sells, MAX(created_at) latest FROM signals").first(),
      env.DB.prepare("SELECT COUNT(*) total FROM trades WHERE status IN ('OPEN','TP1_HIT')").first()
    ]);
    const closed=Number(trade?.closed||0), wins=Number(trade?.wins||0);
    return new Response(JSON.stringify({summary:{total_pnl_pct:Number(trade?.pnl_pct||0),total_pnl_r:Number(trade?.pnl_r||0),win_rate_pct:closed?Math.round(wins/closed*10000)/100:0,total_trades:Number(trade?.total||0),closed_trades:closed,open_trades:Number(open?.total||0),signals:Number(signal?.total||0),buys:Number(signal?.buys||0),sells:Number(signal?.sells||0),latest_signal:signal?.latest||null}}),{headers});
  }catch(e){return new Response(JSON.stringify({error:String(e)}),{status:500,headers});}
}