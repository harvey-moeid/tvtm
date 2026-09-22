export async function onRequest(context) {
  const { env, request }=context;
  const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET,OPTIONS","Content-Type":"application/json"};
  if(request.method==="OPTIONS")return new Response(null,{status:204,headers});
  if(!env.DB)return new Response(JSON.stringify({error:"D1 binding 'DB' tidak ditemukan."}),{status:500,headers});
  const days=Math.min(Math.max(Number(new URL(request.url).searchParams.get("days")||7),1),30);
  try{
    const rows=await env.DB.prepare("SELECT substr(exit_time,1,10) day, COUNT(*) trades, SUM(CASE WHEN pnl_r>0 THEN 1 ELSE 0 END) wins, COALESCE(SUM(pnl_pct),0) pnl_pct, COALESCE(SUM(pnl_r),0) pnl_r FROM trades WHERE status='CLOSED' AND exit_time >= datetime('now', ?) GROUP BY substr(exit_time,1,10) ORDER BY day ASC").bind("-"+days+" days").all();
    const pairs=await env.DB.prepare("SELECT symbol,COUNT(*) trades,COALESCE(SUM(pnl_pct),0) pnl_pct,COALESCE(SUM(pnl_r),0) pnl_r,SUM(CASE WHEN pnl_r>0 THEN 1 ELSE 0 END) wins FROM trades WHERE status='CLOSED' AND exit_time >= datetime('now', ?) GROUP BY symbol ORDER BY pnl_r DESC").bind("-"+days+" days").all();
    return new Response(JSON.stringify({days,by_day:rows.results||[],by_symbol:pairs.results||[]}),{headers});
  }catch(e){return new Response(JSON.stringify({error:String(e)}),{status:500,headers});}
}