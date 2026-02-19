import { defineStore } from 'pinia'
import { http } from '../api/http'

export const useTaskStore = defineStore('task', {
  state: () => ({
    task: {
      jobId: null,
      type: null, // 'parsing', 'paper_gen'
      status: 'idle', // 'idle', 'running', 'done', 'error'
      progress: 0,
      generatedCount: 0,
      totalCount: 0,
      currentStage: '',
      output: '',
      lines: [],
      items: [],
      result: null, // extra result payload from job_done
      sourcePath: '',
      context: {}, // extra context like subject_id
      error: null
    },
    pollingTimer: null,
    typingTimer: null,
    outputQueue: '',
    showPanel: false, // controls if the full panel is visible on the source page
  }),

  actions: {
    startTask({ jobId, type, sourcePath, context = {} }) {
      this.resetTask()
      this.task.jobId = jobId
      this.task.type = type
      this.task.sourcePath = sourcePath
      this.task.context = context
      this.task.status = 'running'
      this.task.currentStage = '准备中...'
      this.showPanel = true
      
      this.pushLine(`任务已创建：${jobId}`)
      this.startPolling()
    },

    resetTask() {
      this.stopPolling()
      this.stopTyping()
      this.task = {
        jobId: null,
        type: null,
        status: 'idle',
        progress: 0,
        generatedCount: 0,
        totalCount: 0,
        currentStage: '',
        output: '',
        lines: [],
        items: [],
        sourcePath: '',
        context: {},
        error: null
      }
      this.outputQueue = ''
      this.showPanel = false
    },

    stopPolling() {
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer)
        this.pollingTimer = null
      }
    },

    stopTyping() {
      if (this.typingTimer) {
        clearInterval(this.typingTimer)
        this.typingTimer = null
      }
      this.outputQueue = ''
    },

    pushLine(text) {
      this.task.lines.push(text)
      if (this.task.lines.length > 2000) {
        this.task.lines.splice(0, this.task.lines.length - 2000)
      }
    },

    enqueueOutput(text) {
      if (!text) return
      this.outputQueue += text
      
      if (!this.typingTimer) {
        this.typingTimer = setInterval(() => {
          if (!this.outputQueue) {
            clearInterval(this.typingTimer)
            this.typingTimer = null
            return
          }
          const backlog = this.outputQueue.length
          const step = Math.min(60, Math.max(1, Math.floor(backlog / 120)))
          const chunk = this.outputQueue.slice(0, step)
          this.outputQueue = this.outputQueue.slice(step)

          this.task.output += chunk
          if (this.task.output.length > 200000) {
            this.task.output = this.task.output.slice(this.task.output.length - 200000)
          }
          
          // Update progress based on output content
          if (this.task.totalCount > 0) {
            const matches = this.task.output.match(/"question_analysis"/g)
            const count = matches ? matches.length : 0
            this.task.generatedCount = Math.max(this.task.generatedCount, count)
            this.task.progress = Math.min(100, Math.floor((this.task.generatedCount / this.task.totalCount) * 100))
          }
        }, 16)
      }
    },

    startPolling() {
      this.stopPolling()
      let lastEventId = 0
      
      this.pollingTimer = setInterval(async () => {
        try {
          const resp = await http.get(`/ai/jobs/${this.task.jobId}`)
          const job = resp.data.job
          if (!job) return
          
          const events = job.events || []
          const newEvents = events.filter(e => (e.id || 0) > lastEventId)
          newEvents.sort((a, b) => (a.id || 0) - (b.id || 0))
          
          for (const ev of newEvents) {
            lastEventId = ev.id || lastEventId
            
            if (ev.type === 'ai_delta') {
              const t = ev?.data?.text || ''
              this.task.currentStage = '正在解析...'
              this.enqueueOutput(t)
            } else {
              const ts = ev.ts ? `【${ev.ts}】` : ''
              const msg = ev.message ? ` ${ev.message}` : ''
              this.pushLine(`${ts}${ev.type}${msg}`)
              
              if (ev.type === 'job_start') {
                 if (ev.data && ev.data.total_count) {
                     this.task.totalCount = ev.data.total_count
                 }
              } else if (ev.type === 'job_done') {
                this.task.status = 'done'
                this.task.currentStage = this.task.type === 'parsing' ? '解析完成' : '生成完成'
                this.task.progress = 100
                this.stopPolling()
                this.stopTyping()
                
                // Flush remaining output
                if (this.outputQueue) {
                    this.task.output += this.outputQueue
                    this.outputQueue = ''
                }

                this.task.items = job.items || []
                this.task.result = ev.data // Save result
                
                // Sync counts with final result
                if (this.task.type === 'parsing') {
                    // For parsing, totalCount is just an estimate, so we sync it to actual result to avoid confusion
                    this.task.generatedCount = this.task.items.length
                    this.task.totalCount = this.task.items.length
                } else {
                    // For generation, use inserted count if available
                    if (job.inserted !== undefined) {
                        this.task.generatedCount = job.inserted
                    } else if (ev.data && ev.data.inserted !== undefined) {
                        this.task.generatedCount = ev.data.inserted
                    } else if (this.task.items.length > 0) {
                         this.task.generatedCount = this.task.items.length
                    }
                    // Sync totalCount to generatedCount if job is done, to avoid confusion like "4/5 (100%)"
                    this.task.totalCount = this.task.generatedCount
                }
              } else if (ev.type === 'job_error') {
                this.task.status = 'error'
                this.task.currentStage = '解析出错'
                this.task.error = ev.message || '未知错误'
                this.stopPolling()
                this.stopTyping()
              } else if (ev.type === 'progress') {
                 if (ev.data && ev.data.inserted) {
                     this.task.generatedCount = ev.data.inserted
                 }
              }
            }
          }
        } catch (e) {
          console.error(e)
        }
      }, 1000)
    }
  }
})
