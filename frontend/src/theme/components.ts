// Component variants following the design brief
export const componentVariants = {
  // Button variants
  Button: {
    variants: {
      primary: {
        bg: 'brand.500',
        color: 'white',
        borderRadius: 'lg',
        fontWeight: 'medium',
        transition: 'all {durations.fast}',
        _hover: {
          bg: 'brand.600',
          transform: 'translateY(-2px)',
          boxShadow: 'lg',
        },
        _active: {
          bg: 'brand.700',
          transform: 'translateY(0)',
        },
        _disabled: {
          opacity: 0.6,
          cursor: 'not-allowed',
          _hover: {
            bg: 'brand.500',
            transform: 'none',
            boxShadow: 'none',
          },
        },
      },
      secondary: {
        bg: 'gray.600',
        color: 'gray.100',
        border: '1px solid',
        borderColor: 'gray.500',
        borderRadius: 'lg',
        fontWeight: 'medium',
        _hover: {
          bg: 'gray.500',
          borderColor: 'gray.400',
        },
        _active: {
          bg: 'gray.700',
        },
      },
      tertiary: {
        bg: 'transparent',
        color: 'brand.500',
        border: '1px solid',
        borderColor: 'brand.500',
        borderRadius: 'lg',
        fontWeight: 'medium',
        _hover: {
          bg: 'brand.50',
          color: 'brand.600',
        },
      },
      ghost: {
        bg: 'transparent',
        color: 'gray.100',
        borderRadius: 'lg',
        fontWeight: 'medium',
        _hover: {
          bg: 'gray.700',
        },
      },
      danger: {
        bg: 'error.500',
        color: 'white',
        borderRadius: 'lg',
        fontWeight: 'medium',
        _hover: {
          bg: '#dc2626',
        },
        _active: {
          bg: '#b91c1c',
        },
      },
    },
    sizes: {
      xs: {
        height: '24px',
        px: 'sm',
        fontSize: 'xs',
      },
      sm: {
        height: '32px',
        px: 'sm',
        fontSize: 'sm',
      },
      md: {
        height: '40px',
        px: 'md',
        fontSize: 'sm',
      },
      lg: {
        height: '48px',
        px: 'lg',
        fontSize: 'sm',
      },
    },
  },

  // Card variants
  Card: {
    variants: {
      default: {
        bg: 'bg.surface',
        border: '1px solid',
        borderColor: 'border',
        borderRadius: 'lg',
        p: 'lg',
        boxShadow: 'sm',
        transition: 'all {durations.normal}',
      },
      interactive: {
        bg: 'bg.surface',
        border: '1px solid',
        borderColor: 'border',
        borderRadius: 'lg',
        p: 'lg',
        boxShadow: 'sm',
        cursor: 'pointer',
        transition: 'all {durations.normal}',
        _hover: {
          boxShadow: 'lg',
          transform: 'translateY(-4px)',
          borderColor: 'border.hover',
        },
        _active: {
          boxShadow: 'md',
          transform: 'translateY(-2px)',
        },
      },
      elevated: {
        bg: 'bg.surface',
        border: '1px solid',
        borderColor: 'border',
        borderRadius: 'lg',
        p: 'lg',
        boxShadow: 'lg',
      },
    },
  },

  // Input variants
  Input: {
    variants: {
      outline: {
        field: {
          bg: 'bg.surface',
          border: '1px solid',
          borderColor: 'border',
          borderRadius: 'md',
          color: 'text',
          fontSize: 'sm',
          height: '40px',
          px: 'sm',
          transition: 'border-color {durations.fast}',
          _placeholder: {
            color: 'text.disabled',
          },
          _hover: {
            borderColor: 'border.hover',
          },
          _focus: {
            borderColor: 'border.focus',
            borderWidth: '2px',
            boxShadow: '0 0 0 1px {colors.brand.500}',
          },
          _invalid: {
            borderColor: 'error.500',
            borderWidth: '2px',
          },
        },
      },
    },
  },

  // Text variants for consistent typography
  Text: {
    variants: {
      h1: {
        fontSize: '3xl',
        fontWeight: 'semibold',
        lineHeight: 'tight',
        letterSpacing: 'tighter',
        color: 'text.heading',
      },
      h2: {
        fontSize: '2xl',
        fontWeight: 'semibold',
        lineHeight: 'snug',
        letterSpacing: 'tighter',
        color: 'text.heading',
      },
      h3: {
        fontSize: 'xl',
        fontWeight: 'semibold',
        lineHeight: 'normal',
        letterSpacing: 'tighter',
        color: 'text.heading',
      },
      h4: {
        fontSize: 'md',
        fontWeight: 'semibold',
        lineHeight: 'relaxed',
        color: 'text.heading',
      },
      body: {
        fontSize: 'sm',
        fontWeight: 'normal',
        lineHeight: 'relaxed',
        color: 'text',
      },
      small: {
        fontSize: 'xs',
        fontWeight: 'normal',
        lineHeight: 'loose',
        color: 'text.muted',
      },
      code: {
        fontSize: 'sm',
        fontWeight: 'medium',
        lineHeight: 'relaxed',
        fontFamily: 'mono',
        letterSpacing: 'wider',
        color: 'text',
      },
      button: {
        fontSize: 'sm',
        fontWeight: 'medium',
        lineHeight: 'relaxed',
      },
    },
  },

  // Modal variants
  Modal: {
    variants: {
      default: {
        dialog: {
          bg: 'bg.surface',
          borderRadius: 'xl',
          boxShadow: 'xl',
          maxW: '500px',
          mx: 'auto',
          my: '10vh',
        },
        overlay: {
          bg: 'rgba(0, 0, 0, 0.6)',
          backdropFilter: 'blur(4px)',
        },
        header: {
          p: 'xl',
          borderBottom: '1px solid',
          borderColor: 'border',
        },
        body: {
          p: 'xl',
        },
        footer: {
          p: 'xl',
          borderTop: '1px solid',
          borderColor: 'border',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 'sm',
        },
      },
    },
  },

  // Table variants
  Table: {
    variants: {
      default: {
        table: {
          bg: 'bg.surface',
          borderRadius: 'lg',
          overflow: 'hidden',
          border: '1px solid',
          borderColor: 'border',
        },
        thead: {
          bg: 'bg.hover',
        },
        th: {
          color: 'text.heading',
          fontWeight: 'semibold',
          fontSize: 'sm',
          p: 'md',
          borderBottom: '1px solid',
          borderColor: 'border',
        },
        td: {
          color: 'text',
          fontSize: 'sm',
          p: 'md',
          borderBottom: '1px solid',
          borderColor: 'border',
        },
        tbody: {
          'tr:hover': {
            bg: 'bg.hover',
          },
          'tr:last-child td': {
            borderBottom: 'none',
          },
        },
      },
    },
  },
} as const;
