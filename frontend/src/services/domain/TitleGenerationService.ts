import { chatService } from '../domains/llm/chatService'
import { frontendLoggingService } from '../frontendLoggingService'
import type { ChatCompletionRequest } from '../domains/llm/chatService'

export interface TitleGenerationResult {
  title: string
  model: string
  success: boolean
}

/**
 * TitleGenerationService - Generate session titles using LLM
 *
 * Handles LLM-based title generation for chat sessions.
 * Extracted from chatTitleGenerator.ts utility.
 *
 * @example
 * ```typescript
 * const titleService = new TitleGenerationService()
 * const result = await titleService.generateTitle('How do I use TypeScript?', 'openai/gpt-4')
 * ```
 */
export class TitleGenerationService {
  /**
   * Generate a session title using LLM API
   *
   * @param assistantMessage - The most recent assistant message in the session
   * @param model - Model identifier in format 'provider/model'
   * @returns Generated title
   * @throws Error if title generation fails
   */
  async generateTitle(assistantMessage: string, model: string): Promise<string> {
    try {
      const prompt = this.buildTitlePrompt(assistantMessage)

      frontendLoggingService.info('TitleGenerationService', 'Sending title generation request', {
        model,
        assistantMessageLength: assistantMessage.length,
        promptLength: prompt.length
      })

      const request: ChatCompletionRequest = {
        model,
        messages: [
          {
            role: 'system',
            content: 'You are a helpful assistant that generates concise, descriptive titles for chat sessions.'
          },
          { role: 'user', content: prompt }
        ],
        options: {
          temperature: 0.3,
          max_tokens: 50
        }
      }

      // Use longer timeout for title generation (30 seconds)
      const response = await chatService.createChatCompletion(request, { timeout: 30000 })

      frontendLoggingService.info('TitleGenerationService', 'Response received', {
        hasData: !!response.data,
        hasChoices: !!response.data?.choices,
        choicesLength: response.data?.choices?.length
      })

      if (response.data && response.data.choices && response.data.choices.length > 0) {
        const rawContent = response.data.choices[0].message.content
        const title = this.extractAndCleanTitle(rawContent)

        frontendLoggingService.info('TitleGenerationService', 'Title generated', {
          title,
          titleLength: title.length
        })

        return title
      }

      throw new Error('No title generated')
    } catch (error) {
      frontendLoggingService.warning('TitleGenerationService', 'Failed to generate session title', {
        error: error instanceof Error ? error.message : String(error)
      })
      throw error
    }
  }

  /**
   * Generate title with fallback to simple extraction
   *
   * @param assistantMessage - The most recent assistant message in the session
   * @param model - Model identifier in format 'provider/model'
   * @returns Generated title or fallback
   */
  async generateTitleWithFallback(assistantMessage: string, model: string): Promise<string> {
    try {
      return await this.generateTitle(assistantMessage, model)
    } catch (error) {
      frontendLoggingService.info('TitleGenerationService', 'Using fallback title', {
        error: error instanceof Error ? error.message : 'Unknown error'
      })
      return this.generateFallbackTitle(assistantMessage)
    }
  }

  /**
   * Generate a fallback title from assistant message content
   *
   * @param assistantMessage - The assistant message
   * @returns Truncated message as title
   */
  generateFallbackTitle(assistantMessage: string): string {
    return assistantMessage.substring(0, 50).trim()
  }

  /**
   * Build the prompt for title generation
   */
  private buildTitlePrompt(assistantMessage: string): string {
    return `Generate a concise, descriptive title (3-7 words) for a chat session based on this assistant's response. The title should capture the main topic or solution discussed. Be specific but brief.

Assistant response: "${assistantMessage}"

Respond with ONLY the title, no explanations or additional text.`
  }

  /**
   * Extract and clean title from LLM response
   */
  private extractAndCleanTitle(rawContent: string | null | undefined): string {
    const title = rawContent?.trim() || ''

    frontendLoggingService.debug('TitleGenerationService', 'Title extracted', {
      rawContent: JSON.stringify(rawContent),
      trimmedTitle: JSON.stringify(title),
      titleLength: title.length
    })

    // Clean up any quotes or extra whitespace
    const cleanedTitle = title.replace(/^["']|["']$/g, '').trim()

    frontendLoggingService.debug('TitleGenerationService', 'Title cleaned', {
      beforeCleanup: JSON.stringify(title),
      afterCleanup: JSON.stringify(cleanedTitle),
      finalLength: cleanedTitle.length
    })

    return cleanedTitle
  }
}
