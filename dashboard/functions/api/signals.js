export async function onRequest(context) {
  const { env, request }=context;
  const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET,OPTIONS","Content-Type":"application/json"};
  if(request.method==="OPTIONS")return new Response(null,{status:204,headers});
  if(!env.DB)return new Response(JSON.stringify({error:"D1 binding 'DB' tidak ditemukan."}),{status:500,headers});
  const u=new URL(request.url),symbol=u.searchParams.get("symbol")||"",direction=u.searchParams.get("direction")||"",limit=Math.min(Math.max(Number(u.searchParams.get("limit")||50),1),100),offset=Math.max(Number(u.searchParams.get("offset")||0),0);
  const where=[],params=[];
  if(symbol){where.push("symbol = ?");params.push(symbol);}
  if(direction){where.push("direction = ?");params.push(direction);}
  const clause=where.length?" WHERE "+where.join(" AND "):"";
  try{
    const data=await env.DB.prepare("SELECT id,signal_key,symbol,market,timeframe,direction,m15_bias,price,zone_type,zone_level,structure_event,pattern,candle_time,stop_loss,take_profit_1,take_profit_2,risk_reward_1,risk_reward_2,confidence_pct,score,checklist_json,notified,created_at FROM signals"+clause+" ORDER BY created_at DESC LIMIT ? OFFSET ?").bind(...params,limit,offset).all();
    const count=await env.DB.prepare("SELECT COUNT(*) total FROM signals"+clause).bind(...params).first();
    return new Response(JSON.stringify({signals:data.results||[],total:Number(count?.total||0),limit,offset}),{headers});
  }catch(e){return new Response(JSON.stringify({error:String(e)}),{status:500,headers});}
}