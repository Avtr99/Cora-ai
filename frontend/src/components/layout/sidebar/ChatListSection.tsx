import React, { useEffect, useRef } from 'react';
import * as ScrollArea from '@radix-ui/react-scroll-area';
import { Virtualizer, VirtualItem } from '@tanstack/react-virtual';
import { IconWrapper } from '@/components/icons/IconWrapper';
import TrashIcon from '@/assets/icons/trash.svg?react';
import { Chat } from '@/store/chatStore.types';

interface ChatListSectionProps {
  chats: Chat[];
  activeChat: Chat | null;
  virtualState: {
    chatListRef: React.RefObject<HTMLDivElement | null>;
    chatVirtualizer: Virtualizer<HTMLDivElement, Element>;
    virtualItems: VirtualItem[];
  };
  uiState: {
    isCollapsed: boolean;
    isMobile: boolean;
    setMobileOpen: (open: boolean) => void;
    focusableIndex: number;
  };
  actions: {
    setFocusedChatIndex: (index: number) => void;
    handleChatKeyDown: (e: React.KeyboardEvent, index: number) => void;
    setActiveChat: (chatId: string) => void;
    handleDeleteChat: (e: React.SyntheticEvent, chatId: string) => void;
  };
}

export const ChatListSection: React.FC<ChatListSectionProps> = ({
  chats,
  activeChat,
  virtualState,
  uiState,
  actions,
}) => {
  const { chatListRef, chatVirtualizer, virtualItems } = virtualState;
  const { isCollapsed, isMobile, setMobileOpen, focusableIndex } = uiState;
  const { setFocusedChatIndex, handleChatKeyDown, setActiveChat, handleDeleteChat } = actions;

  const rowRefs = useRef<Map<string, { title: HTMLButtonElement | null; delete: HTMLButtonElement | null }>>(new Map());

  useEffect(() => {
    const activeChatIds = new Set(chats.map((chat) => chat.id));

    for (const chatId of rowRefs.current.keys()) {
      if (!activeChatIds.has(chatId)) {
        rowRefs.current.delete(chatId);
      }
    }
  }, [chats]);

  if (isCollapsed || chats.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      <p className="text-xs font-semibold text-text-muted uppercase tracking-wider px-5 pt-2 pb-0.5 flex-shrink-0">
        History
      </p>
      <ScrollArea.Root className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea.Viewport
          ref={chatListRef as React.Ref<HTMLDivElement>}
          className="h-full w-full px-3 pb-2"
          role="listbox"
          aria-label="Chat history"
          onWheel={(e) => {
            e.stopPropagation();
          }}
        >
          <div
            style={{
              height: `${chatVirtualizer.getTotalSize()}px`,
              width: '100%',
              position: 'relative',
            }}
          >
            {virtualItems.map((virtualRow) => {
              const chat = chats[virtualRow.index];
              const index = virtualRow.index;

              if (!chat) {
                return null;
              }

              return (
                <div
                  key={chat.id}
                  data-index={virtualRow.index}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: `${virtualRow.size}px`, // Always exactly aligns with virtualizer dimensions
                    transform: `translateY(${virtualRow.start}px)`,
                    paddingBottom: '2px', // Hard geometric 2px space at the bottom of the bounding box
                  }}
                >
                  <div
                    className={`group relative transition-all duration-200 w-full overflow-hidden px-2.5 h-full mx-0.5 rounded-md flex items-center gap-2 ${activeChat?.id === chat.id
                      ? 'bg-surface-subtle/80 text-text-primary shadow-sm'
                      : 'text-text-muted hover:bg-surface-subtle'
                      }`}
                    role="option"
                    aria-selected={activeChat?.id === chat.id}
                    onKeyDown={(e) => {
                      if (e.key === 'Delete') {
                        e.preventDefault();
                        handleDeleteChat(e, chat.id);
                      }
                      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                        const rowButtons = rowRefs.current.get(chat.id);
                        if (!rowButtons) return;

                        if (e.key === 'ArrowRight' && document.activeElement === rowButtons.title) {
                          e.preventDefault();
                          rowButtons.delete?.focus();
                        } else if (e.key === 'ArrowLeft' && document.activeElement === rowButtons.delete) {
                          e.preventDefault();
                          rowButtons.title?.focus();
                        }
                      }
                    }}
                  >
                    <button
                      ref={(el) => {
                        const current = rowRefs.current.get(chat.id) || { title: null, delete: null };
                        rowRefs.current.set(chat.id, { ...current, title: el });
                      }}
                      className={`truncate flex-grow overflow-hidden whitespace-nowrap text-ellipsis font-inter text-xs leading-snug text-left cursor-pointer transition-colors ${activeChat?.id === chat.id ? 'font-medium' : 'font-normal hover:text-text-secondary'
                        }`}
                      onClick={() => {
                        setActiveChat(chat.id);
                        if (isMobile) setMobileOpen(false);
                      }}
                      tabIndex={index === focusableIndex ? 0 : -1}
                      onKeyDown={(e) => handleChatKeyDown(e, index)}
                      onFocus={() => setFocusedChatIndex(index)}
                      aria-label={`Select chat: ${chat.title}`}
                    >
                      {chat.title}
                    </button>
                    <button
                      ref={(el) => {
                        const current = rowRefs.current.get(chat.id) || { title: null, delete: null };
                        rowRefs.current.set(chat.id, { ...current, delete: el });
                      }}
                      className="opacity-0 group-hover:opacity-100 hover:text-semantic-error-icon transition-opacity duration-200 p-1 -mr-1 focus:outline-none focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 flex-shrink-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteChat(e, chat.id);
                      }}
                      aria-label={`Delete chat: ${chat.title}`}
                      data-action="delete-chat"
                      tabIndex={-1}
                    >
                      <IconWrapper Icon={TrashIcon} size={14} aria-hidden={true} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar
          orientation="vertical"
          className="flex select-none touch-none p-0.5 w-1.5 transition-opacity duration-200 opacity-0 hover:opacity-100 data-[state=visible]:opacity-100"
        >
          <ScrollArea.Thumb className="flex-1 bg-border-ui rounded-full relative" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    </div>
  );
};
