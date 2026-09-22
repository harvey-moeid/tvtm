export async function onRequest(context) {
  const { env, request } = context;
  const headers = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET,OPTIONS","Content-Type":"application/json"};
  if (request.method === "OPTIONS") return new Response(null,{status:204,headers});
  if (!env.DB) return new Response(JSON.stringify({error:"D1 binding 'DB' tidak ditemukan."}),{status:500,headers});
  const u=new URL(request.url), symbol=u.searchParams.get("symbol")||"", status=u.searchParams.get("status")||"", limit=Math.min(Math.max(Number(u.searchParams.get("limit")||50),1),100);
  const where=[], params=[];
  if(symbol){where.push("symbol = ?");params.push(symbol);}
  if(status){where.push("status = ?");params.push(status);}
  const clause=where.length?" WHERE "+where.join(" AND "):"";
  try{
    const rows=await env.DB.prepare("SELECT * FROM trades"+clause+" ORDER BY COALESCE(exit_time,entry_time) DESC LIMIT ?").bind(...params,limit).all();
    const stats=await env.DB.prepare("SELECT COUNT(*) total, SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) closed, SUM(CASE WHEN status IN ('OPEN','TP1_HIT') THEN 1 ELSE 0 END) open, COALESCE(SUM(CASE WHEN status='CLOSED' THEN pnl_pct ELSE 0 END),0) pnl_pct, COALESCE(SUM(CASE WHEN status='CLOSED' THEN pnl_r ELSE 0 END),0) pnl_r FROM trades"+clause).bind(...params).first();
    return new Response(JSON.stringify({trades:rows.results||[],stats:{total:Number(stats?.total||0),closed:Number(stats?.closed||0),open:Number(stats?.open||0),pnl_pct:Number(stats?.pnl_pct||0),pnl_r:Number(stats?.pnl_r||0)}}),{headers});
  }catch(e){return new Response(JSON.stringify({error:String(e)}),{status:500,headers});}
}