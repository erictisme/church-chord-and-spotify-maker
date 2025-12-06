// Health check endpoint

export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  return res.status(200).json({
    status: 'ok',
    service: 'church-chord-api',
    timestamp: new Date().toISOString()
  });
}
