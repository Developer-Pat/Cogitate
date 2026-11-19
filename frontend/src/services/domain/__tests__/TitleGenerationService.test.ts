import { describe, it, expect, beforeEach, vi } from 'vitest'
import { TitleGenerationService } from '../TitleGenerationService'
import { chatService } from '@/services/domains/llm/chatService'
import type { ApiResponse } from '@/types'
import type { ChatCompletionResponse } from '@/services/domains/llm/chatService'

// Mock chatService
vi.mock('@/services/domains/llm/chatService', () => ({
  chatService: {
    createChatCompletion: vi.fn()
  }
}))

// Mock frontendLoggingService
vi.mock('@/services/frontendLoggingService', () => ({
  frontendLoggingService: {
    debug: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn()
  }
}))

describe('TitleGenerationService', () => {
  let service: TitleGenerationService

  beforeEach(() => {
    service = new TitleGenerationService()
    vi.clearAllMocks()
  })

  describe('generateTitle', () => {
    it('should generate title from LLM response', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: [
            {
              message: {
                content: '  "TypeScript Best Practices"  '
              }
            }
          ]
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      const title = await service.generateTitle('How do I use TypeScript?', 'openai/gpt-4')

      expect(title).toBe('TypeScript Best Practices')
      expect(chatService.createChatCompletion).toHaveBeenCalledWith(
        expect.objectContaining({
          model: 'openai/gpt-4',
          messages: expect.arrayContaining([
            expect.objectContaining({ role: 'system' }),
            expect.objectContaining({ role: 'user' })
          ]),
          options: expect.objectContaining({
            temperature: 0.3,
            max_tokens: 50
          })
        }),
        expect.objectContaining({ timeout: 30000 })
      )
    })

    it('should clean quotes from title', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: [
            {
              message: {
                content: '"React Hooks Guide"'
              }
            }
          ]
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      const title = await service.generateTitle('Explain React hooks', 'openai/gpt-4')

      expect(title).toBe('React Hooks Guide')
    })

    it('should clean single quotes from title', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: [
            {
              message: {
                content: "'Python Tips'"
              }
            }
          ]
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      const title = await service.generateTitle('Python tips', 'openai/gpt-4')

      expect(title).toBe('Python Tips')
    })

    it('should trim whitespace from title', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: [
            {
              message: {
                content: '   Database Design   '
              }
            }
          ]
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      const title = await service.generateTitle('Design a database', 'openai/gpt-4')

      expect(title).toBe('Database Design')
    })

    it('should throw error when no choices returned', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: []
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      await expect(service.generateTitle('Test', 'openai/gpt-4')).rejects.toThrow('No title generated')
    })

    it('should return empty string when content is null', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: [
            {
              message: {
                content: null
              }
            }
          ]
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      const title = await service.generateTitle('Test', 'openai/gpt-4')

      expect(title).toBe('')
    })

    it('should throw error when API fails', async () => {
      vi.mocked(chatService.createChatCompletion).mockRejectedValue(new Error('Network error'))

      await expect(service.generateTitle('Test', 'openai/gpt-4')).rejects.toThrow('Network error')
    })
  })

  describe('generateTitleWithFallback', () => {
    it('should return LLM title on success', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: [
            {
              message: {
                content: 'API Design Patterns'
              }
            }
          ]
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      const title = await service.generateTitleWithFallback('How to design APIs?', 'openai/gpt-4')

      expect(title).toBe('API Design Patterns')
    })

    it('should return fallback title on API failure', async () => {
      vi.mocked(chatService.createChatCompletion).mockRejectedValue(new Error('API error'))

      const title = await service.generateTitleWithFallback(
        'This is a very long message that should be truncat',
        'openai/gpt-4'
      )

      expect(title).toBe('This is a very long message that should be truncat')
    })
  })

  describe('generateFallbackTitle', () => {
    it('should truncate long messages to 50 characters', () => {
      const longMessage = 'This is a very long message that should be truncat'
      const title = service.generateFallbackTitle(longMessage)

      expect(title).toBe('This is a very long message that should be truncat')
      expect(title.length).toBeLessThanOrEqual(50)
    })

    it('should trim short messages', () => {
      const shortMessage = '  Hello World  '
      const title = service.generateFallbackTitle(shortMessage)

      expect(title).toBe('Hello World')
    })

    it('should handle empty messages', () => {
      const emptyMessage = ''
      const title = service.generateFallbackTitle(emptyMessage)

      expect(title).toBe('')
    })
  })

  describe('buildTitlePrompt', () => {
    it('should build prompt with user message', () => {
      const userMessage = 'How do I use TypeScript?'
      // Access private method via any cast for testing
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const prompt = (service as any).buildTitlePrompt(userMessage)

      expect(prompt).toContain('Generate a concise, descriptive title')
      expect(prompt).toContain('(3-7 words)')
      expect(prompt).toContain(userMessage)
      expect(prompt).toContain('Respond with ONLY the title')
    })
  })

  describe('extractAndCleanTitle', () => {
    it('should handle null content', () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const title = (service as any).extractAndCleanTitle(null)
      expect(title).toBe('')
    })

    it('should handle undefined content', () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const title = (service as any).extractAndCleanTitle(undefined)
      expect(title).toBe('')
    })

    it('should clean and trim content', () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const title = (service as any).extractAndCleanTitle('  "Test Title"  ')
      expect(title).toBe('Test Title')
    })
  })

  describe('integration: full title generation workflow', () => {
    it('should handle complete title generation flow', async () => {
      vi.mocked(chatService.createChatCompletion).mockResolvedValue({
        data: {
          choices: [
            {
              message: {
                content: 'Machine Learning Basics'
              }
            }
          ]
        }
      } as unknown as ApiResponse<ChatCompletionResponse>)

      const title = await service.generateTitle('Explain machine learning', 'anthropic/claude-3')

      expect(title).toBe('Machine Learning Basics')

      // Verify the request was made with correct parameters
      expect(chatService.createChatCompletion).toHaveBeenCalledWith(
        expect.objectContaining({
          model: 'anthropic/claude-3',
          options: expect.objectContaining({
            temperature: 0.3,
            max_tokens: 50
          })
        }),
        expect.objectContaining({ timeout: 30000 })
      )
    })

    it('should handle title generation with fallback', async () => {
      // First call fails, second succeeds
      vi.mocked(chatService.createChatCompletion)
        .mockRejectedValueOnce(new Error('API error'))
        .mockResolvedValueOnce({
          data: {
            choices: [
              {
                message: {
                  content: 'Successful Title'
                }
              }
            ]
          }
        } as unknown as ApiResponse<ChatCompletionResponse>)

      // First attempt uses fallback
      const title1 = await service.generateTitleWithFallback('Test message', 'openai/gpt-4')
      expect(title1).toBe('Test message')

      // Second attempt succeeds
      const title2 = await service.generateTitleWithFallback('Test message 2', 'openai/gpt-4')
      expect(title2).toBe('Successful Title')
    })
  })
})
