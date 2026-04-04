import React, { useState } from "react";
import { 
  LayoutDashboard, 
  Users, 
  Bot, 
  ShieldCheck, 
  ListOrdered, 
  FileSearch, 
  Zap, 
  MessageSquare, 
  Settings,
  Menu,
  X,
  Search,
  RefreshCw,
  LogOut,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export interface SidebarItem {
  key: string;
  label: string;
  icon: React.ElementType;
}

interface AppLayoutProps {
  children: React.ReactNode;
  menuItems: readonly SidebarItem[];
  activeMenuKey: string;
  onMenuChange: (key: string) => void;
  brandTitle: string;
  brandSubtitle?: string;
  headerLeft?: React.ReactNode;
  headerRight?: React.ReactNode;
  onLogout?: () => void;
}

export function AppLayout({
  children,
  menuItems,
  activeMenuKey,
  onMenuChange,
  brandTitle,
  brandSubtitle,
  headerLeft,
  headerRight,
  onLogout
}: AppLayoutProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <TooltipProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        {/* Mobile Overlay */}
        {isMobileMenuOpen && (
          <div 
            className="fixed inset-0 z-40 bg-black/50 lg:hidden" 
            onClick={() => setIsMobileMenuOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside 
          className={cn(
            "fixed inset-y-0 left-0 z-50 flex flex-col bg-card border-r transition-all duration-300 lg:static",
            isSidebarCollapsed ? "w-20" : "w-64",
            isMobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
          )}
        >
          {/* Sidebar Header / Brand */}
          <div className="flex items-center justify-between h-16 px-6 border-b">
            <div className={cn("flex items-center gap-3", isSidebarCollapsed && "justify-center w-full")}>
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground">
                <Bot size={20} />
              </div>
              {!isSidebarCollapsed && (
                <div className="flex flex-col">
                  <span className="font-semibold text-sm leading-tight">{brandTitle}</span>
                  {brandSubtitle && <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{brandSubtitle}</span>}
                </div>
              )}
            </div>
            {!isSidebarCollapsed && (
              <Button 
                variant="ghost" 
                size="icon" 
                className="hidden lg:flex h-8 w-8" 
                onClick={() => setIsSidebarCollapsed(true)}
              >
                <ChevronLeft size={16} />
              </Button>
            )}
          </div>

          {/* Navigation */}
          <ScrollArea className="flex-1 px-3 py-4">
            <nav className="space-y-1">
              {menuItems.map((item) => {
                const isActive = activeMenuKey === item.key;
                const Icon = item.icon;
                
                const content = (
                  <button
                    key={item.key}
                    onClick={() => {
                      onMenuChange(item.key);
                      setIsMobileMenuOpen(false);
                    }}
                    className={cn(
                      "flex items-center w-full rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive 
                        ? "bg-primary text-primary-foreground shadow-sm" 
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                      isSidebarCollapsed && "justify-center px-0"
                    )}
                  >
                    <Icon className={cn("shrink-0", isSidebarCollapsed ? "h-5 w-5" : "h-4 w-4 mr-3")} />
                    {!isSidebarCollapsed && <span>{item.label}</span>}
                  </button>
                );

                if (isSidebarCollapsed) {
                  return (
                    <Tooltip key={item.key} delayDuration={0}>
                      <TooltipTrigger asChild>
                        {content}
                      </TooltipTrigger>
                      <TooltipContent side="right">
                        {item.label}
                      </TooltipContent>
                    </Tooltip>
                  );
                }

                return content;
              })}
            </nav>
          </ScrollArea>

          {/* Sidebar Footer */}
          <div className="p-4 border-t">
            {isSidebarCollapsed ? (
              <div className="flex justify-center">
                <Button variant="ghost" size="icon" onClick={() => setIsSidebarCollapsed(false)}>
                  <ChevronRight size={16} />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-3 px-2">
                <Avatar className="h-9 w-9 border">
                  <AvatarImage src="" />
                  <AvatarFallback className="bg-primary/10 text-primary text-xs">AD</AvatarFallback>
                </Avatar>
                <div className="flex flex-col flex-1 min-w-0">
                  <span className="text-sm font-medium truncate">管理员</span>
                  <span className="text-xs text-muted-foreground truncate">Console Admin</span>
                </div>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground" onClick={onLogout}>
                  <LogOut size={16} />
                </Button>
              </div>
            )}
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          {/* Header */}
          <header className="flex items-center justify-between h-16 px-6 bg-card/80 backdrop-blur-sm border-b z-30">
            <div className="flex items-center gap-4">
              <Button 
                variant="ghost" 
                size="icon" 
                className="lg:hidden" 
                onClick={() => setIsMobileMenuOpen(true)}
              >
                <Menu size={20} />
              </Button>
              <div className="flex items-center gap-4 overflow-x-auto no-scrollbar">
                {headerLeft}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden md:flex relative max-w-sm">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="全局搜索..."
                  className="pl-9 w-[200px] lg:w-[300px] h-9 bg-muted/50 border-none focus-visible:ring-1"
                />
              </div>
              <div className="flex items-center gap-2">
                <ThemeToggle />
                {headerRight}
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-auto bg-muted/30">
            <div className="p-6">
              {children}
            </div>
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
