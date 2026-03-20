<#macro emailLayout>
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      margin: 0;
      padding: 0;
      background-color: #f8f9fa;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #2d3436;
      line-height: 1.6;
    }
    .wrapper {
      width: 100%;
      padding: 40px 16px;
      background-color: #f8f9fa;
    }
    .container {
      max-width: 520px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 4px 24px rgba(0,0,0,0.06);
    }
    .header {
      background: linear-gradient(135deg, #ff6b8a 0%, #ff3d6e 100%);
      padding: 32px;
      text-align: center;
    }
    .header h1 {
      color: #ffffff;
      font-size: 20px;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.3px;
    }
    .header p {
      color: rgba(255,255,255,0.85);
      font-size: 13px;
      margin: 6px 0 0;
    }
    .body {
      padding: 32px;
    }
    .body p {
      margin: 0 0 16px;
      font-size: 14px;
      color: #2d3436;
    }
    .body p:last-child {
      margin-bottom: 0;
    }
    .btn {
      display: inline-block;
      background: linear-gradient(135deg, #ff6b8a 0%, #ff3d6e 100%);
      color: #ffffff !important;
      text-decoration: none;
      padding: 12px 32px;
      border-radius: 24px;
      font-size: 14px;
      font-weight: 600;
      margin: 8px 0 16px;
    }
    .info-box {
      background-color: #f8f9fa;
      border: 1px solid #e0e0e0;
      border-radius: 10px;
      padding: 16px 20px;
      margin: 16px 0;
    }
    .info-box .label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #636e72;
      margin-bottom: 4px;
    }
    .info-box .value {
      font-size: 15px;
      font-weight: 600;
      color: #2d3436;
      word-break: break-all;
    }
    .divider {
      height: 1px;
      background: #e0e0e0;
      margin: 20px 0;
    }
    .footer {
      padding: 20px 32px;
      background-color: #f8f9fa;
      text-align: center;
      border-top: 1px solid #e0e0e0;
    }
    .footer p {
      margin: 0;
      font-size: 12px;
      color: #b2bec3;
    }
    .muted {
      color: #636e72;
      font-size: 13px;
    }
    .link-fallback {
      font-size: 12px;
      color: #636e72;
      word-break: break-all;
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <#nested>
    </div>
  </div>
</body>
</html>
</#macro>
