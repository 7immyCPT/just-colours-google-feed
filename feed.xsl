<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:g="http://base.google.com/ns/1.0">
  <xsl:output method="html" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html>
      <head>
        <title><xsl:value-of select="rss/channel/title"/></title>
        <style>
          body{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5}
          h1{color:#1a73e8;border-bottom:3px solid #1a73e8;padding-bottom:10px}
          .meta{color:#555;margin-bottom:20px;font-size:13px;background:#fff;padding:10px;border-radius:6px;border:1px solid #ddd}
          .product{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:14px;margin-bottom:10px;display:flex;gap:14px;align-items:flex-start;box-shadow:0 1px 3px rgba(0,0,0,.06)}
          .product:hover{box-shadow:0 2px 8px rgba(0,0,0,.12)}
          .product img{width:90px;height:90px;object-fit:contain;border:1px solid #eee;border-radius:6px;background:#fafafa}
          .info{flex:1;min-width:0}
          .info a{font-weight:700;color:#1a73e8;text-decoration:none;font-size:15px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
          .info a:hover{text-decoration:underline}
          .price{margin:5px 0;font-size:16px}
          .price-sale{color:#b71c1c;font-weight:700}
          .price-orig{color:#999;font-size:13px;text-decoration:line-through;margin-left:6px}
          .price-normal{color:#2e7d32;font-weight:700}
          .attrs{font-size:12px;color:#666;margin-top:5px;display:flex;flex-wrap:wrap;gap:5px}
          .badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
          .in{background:#e8f5e9;color:#2e7d32}
          .out{background:#ffebee;color:#c62828}
          .sku{background:#e8eaf6;color:#3949ab}
          .brand{background:#fff3e0;color:#e65100}
          .cat{background:#f3e5f5;color:#7b1fa2}
        </style>
      </head>
      <body>
        <h1><xsl:value-of select="rss/channel/title"/></h1>
        <div class="meta">
          &#128197; <xsl:value-of select="rss/channel/description"/> &#160;&#160;
          &#128230; <strong><xsl:value-of select="count(rss/channel/item)"/></strong> products
        </div>
        <xsl:for-each select="rss/channel/item">
          <div class="product">
            <xsl:if test="g:image_link">
              <img>
                <xsl:attribute name="src"><xsl:value-of select="g:image_link"/></xsl:attribute>
                <xsl:attribute name="alt"><xsl:value-of select="title"/></xsl:attribute>
              </img>
            </xsl:if>
            <div class="info">
              <a>
                <xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute>
                <xsl:attribute name="target">_blank</xsl:attribute>
                <xsl:value-of select="title"/>
              </a>
              <div class="price">
                <xsl:choose>
                  <xsl:when test="g:sale_price">
                    <span class="price-sale"><xsl:value-of select="g:sale_price"/></span>
                    <span class="price-orig"><xsl:value-of select="g:price"/></span>
                  </xsl:when>
                  <xsl:otherwise>
                    <span class="price-normal"><xsl:value-of select="g:price"/></span>
                  </xsl:otherwise>
                </xsl:choose>
              </div>
              <div class="attrs">
                <xsl:choose>
                  <xsl:when test="g:availability='in stock'"><span class="badge in">&#10003; In Stock</span></xsl:when>
                  <xsl:otherwise><span class="badge out">&#10007; Out of Stock</span></xsl:otherwise>
                </xsl:choose>
                <xsl:if test="g:mpn"><span class="badge sku">SKU: <xsl:value-of select="g:mpn"/></span></xsl:if>
                <xsl:if test="g:brand"><span class="badge brand"><xsl:value-of select="g:brand"/></span></xsl:if>
                <xsl:if test="g:product_type"><span class="badge cat"><xsl:value-of select="g:product_type"/></span></xsl:if>
              </div>
            </div>
          </div>
        </xsl:for-each>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>