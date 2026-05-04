"""LLM prompt templates — exact text from the ORACLE build guide.

Never hardcode prompts inside agent files. All five live here so prompt
quality can be tuned without touching pipeline logic.
"""

SENTIMENT_PROMPT = '''
You are analysing Amazon product reviews.
Reviews: {reviews}
Return JSON only, no other text:
{{ "top_complaint": "one sentence max",
  "complaint_frequency": <how many of the reviews mention this complaint, integer>,
  "top_praise": "one sentence max",
  "praise_frequency": <how many mention this praise, integer> }}
'''

HOOK_PROMPT = '''
You are an Amazon listing expert.
Seller title: {seller_title}
Seller first bullet: {seller_bullet}
Competitor titles and bullets: {competitor_hooks}
Rate hook strength 1-10. Return JSON only:
{{ "seller_score": integer,
  "best_competitor_score": integer,
  "gap_reason": "one sentence" }}
'''

LISTING_REWRITE_PROMPT = '''
You are a professional Amazon copywriter.
Current bullet: {current_bullet}
Keywords to add: {keywords}
Issue to fix: {issue}
Rewrite this bullet point. Rules:
- Include all keywords naturally
- Start with the strongest benefit
- Under 200 characters
- Output the rewritten bullet only. No preamble. No explanation.
'''

REVIEW_REPLY_PROMPT = '''
You are a professional Amazon seller responding to customer feedback.
Most common complaint: {complaint}
Number of customers mentioning it: {frequency}
Write a public reply to post on Amazon. Rules:
- Acknowledge the complaint specifically
- Offer a concrete resolution
- Under 100 words
- Professional and warm tone
- Output the reply only. No preamble.
'''

PRICING_REWRITE_PROMPT = '''
You are a pricing strategist for an Amazon multi-marketplace seller.
The seller has the same product listed in several Amazon marketplaces. After
converting all prices to USD using current FX rates, here is what we see:

Pricing data (USD-equivalent):
{pricing_data}

Detected issue: {issue}

Write a one-paragraph recommendation.
Rules:
- Name the specific marketplace and the new price (in local currency)
- Justify with the percentage gap and the reasoning (undercut, capture margin, FX shift)
- Under 90 words
- Output the recommendation only. No preamble. No bullet points.
'''

SOCIAL_PROMPT = '''
You are a social media copywriter for an Amazon brand.
Product: {product_title}
Key differentiator competitors are missing: {gap}
Write an Instagram caption. Rules:
- Lead with the differentiator as a hook
- Under 150 words
- End with 3 relevant hashtags
- Output the caption only. No preamble.
'''
