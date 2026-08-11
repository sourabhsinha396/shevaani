"use client"

import { useEffect, useState } from "react"
import { AnimatePresence, motion, type MotionProps } from "motion/react"

import { cn } from "@/lib/utils"

interface WordRotateProps {
  words: string[]
  duration?: number
  motionProps?: MotionProps
  className?: string
}

/**
 * Magic UI's WordRotate, changed in one way: it renders an inline `span`
 * instead of an `h1`, so it can sit inside a headline rather than replace one.
 * The track is `inline-grid` with every word stacked in the same cell, which
 * reserves the width of the longest word and stops the line reflowing on each
 * swap.
 */
export function WordRotate({
  words,
  duration = 2500,
  motionProps = {
    initial: { opacity: 0, y: "-0.35em" },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: "0.35em" },
    transition: { duration: 0.3, ease: "easeOut" },
  },
  className,
}: WordRotateProps) {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((prevIndex) => (prevIndex + 1) % words.length)
    }, duration)

    // Clean up interval on unmount
    return () => clearInterval(interval)
  }, [words, duration])

  return (
    // No `overflow-hidden` here, deliberately: an inline box with a clipped
    // overflow takes its baseline from its bottom margin edge, which drops the
    // rotating word off the headline's baseline. The words fade rather than
    // being wiped, so there is nothing to clip anyway.
    <span className="relative inline-grid align-baseline">
      {/* Invisible sizer: the longest word holds the cell open. */}
      {words.map((word) => (
        <span
          key={word}
          aria-hidden
          className={cn("invisible col-start-1 row-start-1", className)}
        >
          {word}
        </span>
      ))}
      {/* `initial={false}` so the first word is painted opaque rather than
          animated in - the headline must be readable even if the animation
          never runs. */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={words[index]}
          className={cn("col-start-1 row-start-1", className)}
          {...motionProps}
        >
          {words[index]}
        </motion.span>
      </AnimatePresence>
    </span>
  )
}
