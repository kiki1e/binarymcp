import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import 'highlight.js/styles/github-dark.css'

interface MarkdownRendererProps {
  content: string
  className?: string
}

export default function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight, rehypeRaw]}
        components={{
          h1: ({ children }) => <h1 className="text-2xl font-bold text-gray-900 dark:text-white mt-6 mb-4">{children}</h1>,
          h2: ({ children }) => <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mt-5 mb-3">{children}</h2>,
          h3: ({ children }) => <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mt-4 mb-2">{children}</h3>,
          h4: ({ children }) => <h4 className="text-base font-semibold text-gray-700 dark:text-gray-300 mt-3 mb-2">{children}</h4>,
          p: ({ children }) => <p className="text-gray-800 dark:text-gray-300 mb-3 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="list-disc list-inside mb-3 space-y-1 text-gray-800 dark:text-gray-300">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside mb-3 space-y-1 text-gray-800 dark:text-gray-300">{children}</ol>,
          li: ({ children }) => <li className="ml-4">{children}</li>,
          code: ({ inline, className, children, ...props }: any) => {
            if (inline) {
              return <code className="bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>{children}</code>
            }
            return <code className={`${className} text-sm`} {...props}>{children}</code>
          },
          pre: ({ children }) => <pre className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 overflow-x-auto mb-4 border border-gray-200 dark:border-gray-800">{children}</pre>,
          blockquote: ({ children }) => <blockquote className="border-l-4 border-gray-300 dark:border-gray-700 pl-4 italic text-gray-600 dark:text-gray-400 my-3">{children}</blockquote>,
          a: ({ href, children }) => <a href={href} className="text-gray-900 dark:text-gray-100 underline hover:text-gray-600 dark:hover:text-gray-300" target="_blank" rel="noopener noreferrer">{children}</a>,
          table: ({ children }) => <div className="overflow-x-auto mb-4"><table className="min-w-full border border-gray-200 dark:border-gray-800">{children}</table></div>,
          thead: ({ children }) => <thead className="bg-gray-100 dark:bg-gray-800">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-gray-200 dark:divide-gray-800">{children}</tbody>,
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => <th className="px-4 py-2 text-left text-sm font-semibold text-gray-900 dark:text-white">{children}</th>,
          td: ({ children }) => <td className="px-4 py-2 text-sm text-gray-800 dark:text-gray-300">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
