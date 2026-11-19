#!/usr/bin/env node

/**
 * Check OpenRouter API Key Limits and Usage
 * 
 * Usage: node check-openrouter-limits.js
 * 
 * Requires: OPENROUTER_API_KEY in environment or .env file
 */

import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// Try to load .env files
const envPaths = [
  join(__dirname, '..', '.env'),
  join(__dirname, '..', 'backend', '.env'),
]

let loaded = false
for (const envPath of envPaths) {
  try {
    const envContent = readFileSync(envPath, 'utf-8')
    envContent.split('\n').forEach(line => {
      const [key, value] = line.split('=')
      if (key && value && key.includes('OPENROUTER')) {
        process.env[key.trim()] = value.trim()
      }
    })
    console.log(`✅ Loaded ${envPath}`)
    loaded = true
  } catch (error) {
    // Try next path
  }
}

if (!loaded) {
  console.log('⚠️  No .env file found, using environment variables')
}

const API_KEY = process.env.OPENROUTER_API_KEY

if (!API_KEY) {
  console.error('❌ Error: OPENROUTER_API_KEY not found')
  console.error('Please set it in your .env file or environment')
  process.exit(1)
}

async function checkLimits() {
  console.log('🔍 Checking OpenRouter API key limits...\n')
  
  try {
    const response = await fetch('https://openrouter.ai/api/v1/key', {
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
      }
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
    const keyInfo = data.data

    console.log('📊 OpenRouter API Key Status')
    console.log('═'.repeat(50))
    console.log(`Label: ${keyInfo.label || 'Unnamed'}`)
    console.log('')
    
    // Account tier
    console.log(`🎯 Account Type: ${keyInfo.is_free_tier ? 'Free Tier' : 'Paid'}`)
    console.log('')

    // Credit limits
    console.log('💰 Credit Limits:')
    if (keyInfo.limit === null) {
      console.log('   Limit: Unlimited ✅')
    } else {
      console.log(`   Limit: ${keyInfo.limit.toFixed(2)} credits`)
      console.log(`   Remaining: ${keyInfo.limit_remaining?.toFixed(2) || 'N/A'} credits`)
      console.log(`   Reset: ${keyInfo.limit_reset || 'Never'}`)
    }
    console.log('')

    // Usage statistics
    console.log('📈 Usage Statistics:')
    console.log(`   Total (all-time): ${keyInfo.usage.toFixed(4)} credits`)
    console.log(`   Today (UTC): ${keyInfo.usage_daily.toFixed(4)} credits`)
    console.log(`   This Week: ${keyInfo.usage_weekly.toFixed(4)} credits`)
    console.log(`   This Month: ${keyInfo.usage_monthly.toFixed(4)} credits`)
    console.log('')

    // Free tier specific info
    if (keyInfo.is_free_tier) {
      console.log('🆓 Free Tier Information:')
      console.log('   Daily limit for :free models: 50 requests/day')
      console.log('   Upgrade to 1000/day with $10+ credit purchase')
      console.log('   Per-minute rate limit: 20 requests/minute')
      console.log('')
    }

    // BYOK usage (if applicable)
    if (keyInfo.byok_usage > 0) {
      console.log('🔗 External BYOK Usage:')
      console.log(`   Total: ${keyInfo.byok_usage.toFixed(4)} credits`)
      console.log(`   Today: ${keyInfo.byok_usage_daily.toFixed(4)} credits`)
      console.log(`   This Week: ${keyInfo.byok_usage_weekly.toFixed(4)} credits`)
      console.log(`   This Month: ${keyInfo.byok_usage_monthly.toFixed(4)} credits`)
      console.log('')
    }

    // Recommendations
    console.log('💡 Recommendations:')
    if (keyInfo.is_free_tier) {
      if (keyInfo.usage_daily > 40) {
        console.log('   ⚠️  Approaching daily free tier limit!')
        console.log('   Consider purchasing $10 in credits for higher limits')
      } else if (keyInfo.usage_daily > 20) {
        console.log('   ✅ Good usage level for development')
        console.log('   Monitor to avoid hitting 50 request limit')
      } else {
        console.log('   ✅ Well within free tier limits')
        console.log('   Plenty of room for development testing')
      }
    } else {
      console.log('   ✅ Paid account - higher limits apply')
      if (keyInfo.limit_remaining && keyInfo.limit_remaining < 5) {
        console.log('   ⚠️  Low credit balance - consider topping up')
      }
    }

    console.log('')
    console.log('═'.repeat(50))
    console.log('📚 More info: https://openrouter.ai/docs/credits')
    console.log('')

  } catch (error) {
    console.error('❌ Error checking limits:', error.message)
    console.error('')
    console.error('Possible issues:')
    console.error('1. Invalid API key')
    console.error('2. Network connection problem')
    console.error('3. OpenRouter API temporarily unavailable')
    console.error('')
    console.error('Check your OPENROUTER_API_KEY in .env file')
    process.exit(1)
  }
}

// Run the check
checkLimits()
